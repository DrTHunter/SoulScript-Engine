"""Tests for the ModelRouter, BudgetTracker, ContextManager, and TickScheduler.

Validates:
  - Task classification logic
  - Tier routing decisions
  - Stuck loop escalation
  - Budget enforcement (hard/soft limits)
  - Budget month rollover
  - Context window trimming
  - Working set management
  - TickScheduler finite loop completion
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from src.routing.model_router import (
    ModelRouter,
    Tier,
    TierConfig,
    TIER_NAMES,
    TaskType,
    classify_task,
    RoutingDecision,
)
from src.routing.budget_tracker import BudgetTracker, BudgetState
from src.routing.context_manager import ContextManager, ContextBudget, WorkingSet
from src.routing.tick_scheduler import TickScheduler, ScheduleConfig, LoopStatus


# ------------------------------------------------------------------
# Task classification tests
# ------------------------------------------------------------------

class TestClassifyTask(unittest.TestCase):
    def test_coding_keywords(self):
        result = classify_task("Please debug this function error")
        self.assertEqual(result, TaskType.CODING)

    def test_summarization_keywords(self):
        result = classify_task("Summarize the meeting notes")
        self.assertEqual(result, TaskType.SUMMARIZATION)

    def test_planning_keywords(self):
        result = classify_task("Create a roadmap for the project")
        self.assertEqual(result, TaskType.PLANNING)

    def test_high_stakes_keywords(self):
        result = classify_task("Deploy to production with migration")
        self.assertEqual(result, TaskType.HIGH_STAKES)

    def test_memory_ops_keywords(self):
        result = classify_task("Recall what I said about memory")
        self.assertEqual(result, TaskType.MEMORY_OPS)

    def test_general_fallback(self):
        result = classify_task("Hello how are you today")
        self.assertEqual(result, TaskType.GENERAL)

    def test_explicit_type_override(self):
        result = classify_task("Hello world", explicit_type=TaskType.CODING)
        self.assertEqual(result, TaskType.CODING)

    def test_errors_boost_coding(self):
        result = classify_task("Check the output", recent_errors=["SyntaxError", "NameError"])
        self.assertEqual(result, TaskType.CODING)


# ------------------------------------------------------------------
# ModelRouter tests
# ------------------------------------------------------------------

def _make_tier_configs():
    return {
        Tier.LOCAL_CHEAP: TierConfig(
            tier=Tier.LOCAL_CHEAP, provider="ollama", model="qwen2.5:7b",
            base_url="http://localhost:11434", enabled=True,
        ),
        Tier.LOCAL_STRONG: TierConfig(
            tier=Tier.LOCAL_STRONG, provider="ollama", model="llama3:70b",
            base_url="http://localhost:11434", enabled=True,
        ),
        Tier.CHEAP_CLOUD: TierConfig(
            tier=Tier.CHEAP_CLOUD, provider="deepseek", model="deepseek-chat",
            base_url="https://api.deepseek.com/v1", enabled=True,
        ),
        Tier.EXPENSIVE_CLOUD: TierConfig(
            tier=Tier.EXPENSIVE_CLOUD, provider="openai", model="gpt-5.2",
            base_url="https://api.openai.com/v1", enabled=True,
        ),
    }


class TestModelRouter(unittest.TestCase):
    def setUp(self):
        self.configs = _make_tier_configs()
        self.router = ModelRouter(self.configs)

    def test_general_task_routes_to_local_cheap(self):
        decision = self.router.route("Hello there")
        self.assertEqual(decision.tier, Tier.LOCAL_CHEAP)
        self.assertEqual(decision.task_type, TaskType.GENERAL)

    def test_coding_task_routes_to_cheap_cloud(self):
        decision = self.router.route("Debug this function please")
        self.assertEqual(decision.tier, Tier.CHEAP_CLOUD)
        self.assertEqual(decision.task_type, TaskType.CODING)

    def test_final_polish_routes_to_expensive(self):
        decision = self.router.route("Final review and polish this code")
        self.assertEqual(decision.tier, Tier.EXPENSIVE_CLOUD)
        self.assertEqual(decision.task_type, TaskType.FINAL_POLISH)

    def test_stuck_loop_escalation(self):
        """Same error 3 times should escalate one tier."""
        errors = ["SyntaxError: invalid syntax"]
        # First two calls shouldn't escalate
        self.router.route("fix code", recent_errors=errors)
        self.router.route("fix code", recent_errors=errors)
        # Third should escalate
        decision = self.router.route("fix code", recent_errors=errors)
        # Should have escalated from cheap_cloud
        self.assertGreater(decision.tier, Tier.LOCAL_CHEAP)

    def test_force_tier(self):
        decision = self.router.route("Hello", force_tier=Tier.EXPENSIVE_CLOUD)
        self.assertEqual(decision.tier, Tier.EXPENSIVE_CLOUD)

    def test_skip_disabled_tiers(self):
        self.configs[Tier.LOCAL_CHEAP].enabled = False
        router = ModelRouter(self.configs)
        decision = router.route("Hello there")
        # Should skip to next enabled tier
        self.assertGreaterEqual(decision.tier, Tier.LOCAL_STRONG)

    def test_budget_gate_forces_local(self):
        budget = MagicMock()
        budget.remaining.return_value = 0
        budget.is_hard_limit_hit.return_value = False
        budget.is_soft_limit_hit.return_value = False
        router = ModelRouter(self.configs, budget_tracker=budget)

        budget.remaining.return_value = 0
        decision = router.route("Debug this code")
        # Remaining is 0, should force down to local
        self.assertLessEqual(decision.tier, Tier.LOCAL_STRONG)

    def test_soft_limit_caps_at_cheap_cloud(self):
        budget = MagicMock()
        budget.remaining.return_value = 2.0
        budget.is_hard_limit_hit.return_value = False
        budget.is_soft_limit_hit.return_value = True
        router = ModelRouter(self.configs, budget_tracker=budget)

        decision = router.route("Final review and polish the code")
        # soft limit should cap at cheap_cloud
        self.assertLessEqual(decision.tier, Tier.CHEAP_CLOUD)

    def test_from_config(self):
        cfg = {
            "enabled": True,
            "tiers": {
                "local_cheap": {
                    "provider": "ollama",
                    "model": "qwen2.5:7b",
                    "enabled": True,
                },
                "cheap_cloud": {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "enabled": True,
                },
            },
            "task_overrides": {
                "coding": "cheap_cloud",
            },
        }
        router = ModelRouter.from_config(cfg)
        self.assertIn(Tier.LOCAL_CHEAP, router.tier_configs)
        self.assertIn(Tier.CHEAP_CLOUD, router.tier_configs)
        self.assertEqual(router.task_min_tiers[TaskType.CODING], Tier.CHEAP_CLOUD)


# ------------------------------------------------------------------
# BudgetTracker tests
# ------------------------------------------------------------------

class TestBudgetTracker(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "budget_state.json")

    def test_initial_state(self):
        bt = BudgetTracker(state_path=self.state_path)
        self.assertEqual(bt.remaining(), 20.00)
        self.assertFalse(bt.is_hard_limit_hit())
        self.assertFalse(bt.is_soft_limit_hit())

    def test_record_cost(self):
        bt = BudgetTracker(state_path=self.state_path)
        bt.record_cost(5.00, "cheap_cloud")
        self.assertAlmostEqual(bt.state.monthly_spent, 5.00)
        self.assertAlmostEqual(bt.remaining(), 15.00)

    def test_hard_limit(self):
        bt = BudgetTracker(monthly_hard_cap=10.0, state_path=self.state_path)
        bt.record_cost(10.01, "expensive_cloud")
        self.assertTrue(bt.is_hard_limit_hit())

    def test_soft_limit(self):
        bt = BudgetTracker(monthly_hard_cap=10.0, monthly_soft_cap=8.0,
                           state_path=self.state_path)
        bt.record_cost(8.50, "expensive_cloud")
        self.assertTrue(bt.is_soft_limit_hit())
        self.assertFalse(bt.is_hard_limit_hit())

    def test_session_limit(self):
        bt = BudgetTracker(per_session_cap=1.0, state_path=self.state_path)
        bt.record_cost(1.50, "cheap_cloud")
        self.assertTrue(bt.is_session_limit_hit())

    def test_reset_session(self):
        bt = BudgetTracker(state_path=self.state_path)
        bt.record_cost(1.00, "cheap_cloud")
        bt.reset_session()
        self.assertAlmostEqual(bt.state.session_spent, 0.0)
        # Monthly should still be tracked
        self.assertAlmostEqual(bt.state.monthly_spent, 1.00)

    def test_tick_budget_check(self):
        bt = BudgetTracker(monthly_hard_cap=1.0, per_tick_cap=0.10,
                           state_path=self.state_path)
        self.assertIsNone(bt.check_tick_budget(0.05))
        self.assertIsNotNone(bt.check_tick_budget(0.15))  # exceeds per-tick
        bt.record_cost(1.01, "expensive_cloud")
        self.assertIsNotNone(bt.check_tick_budget(0.01))  # budget exhausted

    def test_persistence(self):
        bt1 = BudgetTracker(state_path=self.state_path)
        bt1.record_cost(3.50, "cheap_cloud")

        bt2 = BudgetTracker(state_path=self.state_path)
        self.assertAlmostEqual(bt2.state.monthly_spent, 3.50)

    def test_tier_spending_breakdown(self):
        bt = BudgetTracker(state_path=self.state_path)
        bt.record_cost(1.00, "cheap_cloud")
        bt.record_cost(2.00, "expensive_cloud")
        bt.record_cost(0.50, "cheap_cloud")
        self.assertAlmostEqual(bt.state.tier_spending["cheap_cloud"], 1.50)
        self.assertAlmostEqual(bt.state.tier_spending["expensive_cloud"], 2.00)

    def test_summary(self):
        bt = BudgetTracker(state_path=self.state_path)
        bt.record_cost(1.00, "cheap_cloud")
        summary = bt.get_summary()
        self.assertIn("monthly_spent", summary)
        self.assertIn("remaining", summary)
        self.assertIn("hard_limit_hit", summary)

    def test_from_config(self):
        cfg = {"monthly_hard_cap": 50.0, "per_tick_cap": 0.25}
        bt = BudgetTracker.from_config(cfg)
        self.assertAlmostEqual(bt.state.monthly_hard_cap, 50.0)
        self.assertAlmostEqual(bt.state.per_tick_cap, 0.25)


# ------------------------------------------------------------------
# ContextManager tests
# ------------------------------------------------------------------

class TestContextManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ws_path = os.path.join(self.tmpdir, "working_set.json")

    def test_trim_within_budget(self):
        cm = ContextManager(window_size=5)
        msgs = [{"role": "system", "content": "You are an AI."}]
        msgs += [{"role": "user", "content": f"msg {i}"} for i in range(3)]
        trimmed = cm.trim_messages(msgs, "local_cheap")
        self.assertEqual(len(trimmed), 4)  # system + 3 user

    def test_trim_rolling_window(self):
        cm = ContextManager(window_size=5)
        msgs = [{"role": "system", "content": "You are an AI."}]
        msgs += [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        trimmed = cm.trim_messages(msgs, "cheap_cloud")
        self.assertEqual(len(trimmed), 6)  # system + last 5

    def test_working_set_persistence(self):
        cm = ContextManager(working_set_path=self.ws_path)
        cm.update_working_set(5, objectives=["Build feature X"], decision="Use Python")
        cm.save_working_set()

        cm2 = ContextManager(working_set_path=self.ws_path)
        self.assertEqual(cm2.working_set.tick_count, 5)
        self.assertEqual(cm2.working_set.objectives, ["Build feature X"])

    def test_should_compact(self):
        cm = ContextManager(compaction_interval=10)
        self.assertFalse(cm.should_compact(0))
        self.assertFalse(cm.should_compact(5))
        self.assertTrue(cm.should_compact(10))

    def test_compact_creates_summary(self):
        cm = ContextManager(window_size=5, working_set_path=self.ws_path)
        msgs = [{"role": "system", "content": "sys"}]
        msgs += [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        summary = cm.compact(msgs, tick_index=10, summary="Test compaction")
        self.assertEqual(summary, "Test compaction")
        self.assertEqual(len(cm.working_set.compaction_summaries), 1)

    def test_working_set_to_system_block(self):
        ws = WorkingSet(objectives=["Goal A"], recent_decisions=["Decision B"])
        block = ws.to_system_block()
        self.assertIn("Goal A", block)
        self.assertIn("Decision B", block)

    def test_context_budget_levels(self):
        cm = ContextManager()
        msgs = [{"role": "system", "content": "s"}]
        cm.trim_messages(msgs, "local_cheap")
        self.assertEqual(cm.budget.current_limit, 4000)
        cm.trim_messages(msgs, "cheap_cloud")
        self.assertEqual(cm.budget.current_limit, 16000)
        cm.trim_messages(msgs, "expensive_cloud")
        self.assertEqual(cm.budget.current_limit, 64000)


# ------------------------------------------------------------------
# TickScheduler tests
# ------------------------------------------------------------------

class TestTickScheduler(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "agi_loop_state.json")

    def test_initial_state(self):
        config = ScheduleConfig(max_loops=5)
        scheduler = TickScheduler(config=config, state_path=self.state_path)
        status = scheduler.get_status()
        self.assertEqual(status["status"], LoopStatus.IDLE)
        self.assertEqual(status["max_loops"], 5)

    def test_config_interval(self):
        config = ScheduleConfig(interval_hours=1, interval_minutes=30)
        self.assertEqual(config.interval_seconds, 5400)

    def test_infinite_flag(self):
        config = ScheduleConfig(max_loops=0)
        scheduler = TickScheduler(config=config, state_path=self.state_path)
        self.assertTrue(scheduler.get_status()["is_infinite"])

    def test_finite_flag(self):
        config = ScheduleConfig(max_loops=10)
        scheduler = TickScheduler(config=config, state_path=self.state_path)
        self.assertFalse(scheduler.get_status()["is_infinite"])

    def test_update_config(self):
        config = ScheduleConfig(max_loops=5)
        scheduler = TickScheduler(config=config, state_path=self.state_path)
        scheduler.update_config({"max_loops": 10, "interval_minutes": 15})
        self.assertEqual(scheduler.config.max_loops, 10)
        self.assertEqual(scheduler.config.interval_minutes, 15)

    def test_state_persistence(self):
        config = ScheduleConfig(max_loops=5)
        scheduler = TickScheduler(config=config, state_path=self.state_path)
        scheduler.state.loops_completed = 3
        scheduler.state.total_cost = 1.50
        scheduler._save_state()

        scheduler2 = TickScheduler(config=config, state_path=self.state_path)
        self.assertEqual(scheduler2.state.loops_completed, 3)
        self.assertAlmostEqual(scheduler2.state.total_cost, 1.50)

    def test_finite_loop_completes(self):
        """Run a scheduler with 2 loops, 1 tick each, verify it completes."""
        mock_outcomes = [MagicMock(
            errors=[],
            metering={"cost": {"total_cost": 0.001}},
            outcome_summary="Test tick done",
            tools_used=[],
        )]

        def mock_run(profile_name, ticks_per_loop, max_steps_per_tick, stimulus):
            return mock_outcomes

        config = ScheduleConfig(
            max_loops=2,
            ticks_per_loop=1,
            interval_hours=0,
            interval_minutes=0,
        )
        scheduler = TickScheduler(
            config=config,
            run_fn=mock_run,
            state_path=self.state_path,
        )
        scheduler.start()
        # Wait for completion
        scheduler._thread.join(timeout=10)
        self.assertEqual(scheduler.state.loops_completed, 2)
        self.assertEqual(scheduler.state.status, LoopStatus.STOPPED)

    def test_pause_resume(self):
        config = ScheduleConfig(max_loops=0)
        scheduler = TickScheduler(config=config, state_path=self.state_path)
        scheduler.pause()
        self.assertEqual(scheduler.state.status, LoopStatus.PAUSED)
        scheduler.resume()
        self.assertEqual(scheduler.state.status, LoopStatus.RUNNING)

    def test_from_config(self):
        cfg = {
            "interval_hours": 2,
            "interval_minutes": 15,
            "max_loops": 100,
            "ticks_per_loop": 10,
            "profile": "elysia",
        }
        scheduler = TickScheduler.from_config(cfg)
        self.assertEqual(scheduler.config.interval_hours, 2)
        self.assertEqual(scheduler.config.max_loops, 100)
        self.assertEqual(scheduler.config.profile, "elysia")


if __name__ == "__main__":
    unittest.main()
