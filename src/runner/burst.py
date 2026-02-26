"""Burst Runner — run an agent linearly for N ticks.

Each tick is a bounded mini-loop (see ``tick.py``).  Exceptions at any
level are caught, logged to the journal, and execution continues with
the next tick.

Usage (programmatic):
    from src.runner.burst import run_burst

    outcomes = run_burst(profile_name="orion", burst_ticks=15)

Usage (CLI):
    python -m src.run_burst --profile orion --burst-ticks 15
"""

import json
import os
import time
from typing import List, Optional

import yaml

from src.llm_client.base import LLMClient
from src.llm_client.factory import create_client
from src.memory.faiss_memory import FAISSMemory
from src.policy.boundary import BoundaryLogger
from src.runner.tick import run_tick
from src import data_paths
from src.runner.types import BurstConfig, TickOutcome
from src.runtime_policy import RuntimePolicy
from src.tools.runtime_info_tool import RuntimeInfoTool
from src.observability.metering import Metering, zero_metering


# ------------------------------------------------------------------
# Profile loading (mirrors loop.py, self-contained for burst use)
# ------------------------------------------------------------------

def _load_profile(name: str) -> dict:
    path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "profiles", f"{name}.yaml")
    )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def run_burst(
    profile_name: str,
    burst_ticks: int = 15,
    max_steps_per_tick: int = 3,
    stimulus: str = "",
    client: Optional[LLMClient] = None,
    vault: Optional[FAISSMemory] = None,
) -> List[TickOutcome]:
    """Execute *burst_ticks* ticks linearly for the given profile.

    Parameters
    ----------
    profile_name:
        Name of a YAML profile in ``profiles/``.
    burst_ticks:
        Number of ticks to run (default 15).
    max_steps_per_tick:
        Model calls per tick (default 3).
    stimulus:
        Optional seed message injected into each tick.
    client:
        Optional pre-built LLM client (useful for testing with mocks).
    vault:
        Optional pre-built FAISSMemory (useful for testing with temp dirs).

    Returns
    -------
    List of ``TickOutcome`` objects, one per tick.
    """
    profile = _load_profile(profile_name)

    config = BurstConfig(
        profile=profile_name,
        burst_ticks=burst_ticks,
        max_steps_per_tick=max_steps_per_tick,
        stimulus=stimulus,
    )

    # --- Resolve dependencies ---
    if client is None:
        client = create_client(profile)

    if vault is None:
        mem_cfg = profile.get("memory", {})
        if mem_cfg.get("enabled", False):
            vault = FAISSMemory(
                vault_path=data_paths.vault_path(),
                faiss_dir=data_paths.faiss_dir(),
            )

    boundary_logger = BoundaryLogger(data_paths.boundary_events_path())

    # --- Set runtime_info context for burst mode ---
    policy_cfg = profile.get("policy", {})
    burst_policy = RuntimePolicy(
        max_iterations=policy_cfg.get("max_iterations", 25),
        max_wall_time_seconds=policy_cfg.get("max_wall_time_seconds"),
        stasis_mode=policy_cfg.get("stasis_mode", False),
        tool_failure_mode=policy_cfg.get("tool_failure_mode", "continue"),
    )
    RuntimeInfoTool.set_context(profile, burst_policy, execution_mode="burst")

    # --- Log burst start ---
    burst_id = f"burst_{int(time.time())}"

    print(
        f"[burst] Starting | profile={profile_name} ticks={burst_ticks} "
        f"max_steps={max_steps_per_tick}"
    )

    # --- Tick loop ---
    outcomes: List[TickOutcome] = []
    burst_metering = zero_metering()

    for i in range(burst_ticks):
        print(f"[tick-start] {json.dumps({'tick': i, 'total': burst_ticks})}", flush=True)

        try:
            outcome = run_tick(
                profile=profile,
                client=client,
                vault=vault,
                config=config,
                tick_index=i,
                stimulus=stimulus,
                boundary_logger=boundary_logger,
            )
        except Exception as exc:
            # Catch-all: tick itself should never raise, but be defensive
            outcome = TickOutcome(
                tick_index=i,
                errors=[f"tick_exception: {exc}"],
                stop_reason="unhandled_exception",
                outcome_summary=f"Tick {i} failed with unhandled exception: {exc}",
            )

        outcomes.append(outcome)

        # Accumulate metering
        if outcome.metering:
            burst_metering = burst_metering + Metering.from_dict(outcome.metering)

        # Console feedback
        err_tag = f" ERRORS={len(outcome.errors)}" if outcome.errors else ""
        inbox_tag = " inbox=sent" if any(t.startswith("creator_inbox") for t in outcome.tools_used) else ""
        tools_str = ",".join(outcome.tools_used) if outcome.tools_used else "none"
        cost_tag = ""
        if outcome.metering:
            tick_cost = outcome.metering.get("cost", {}).get("total_cost", 0)
            if tick_cost > 0:
                cost_tag = f" cost=${tick_cost:.4f}"
        tick_end_data = {
            "tick": i,
            "total": burst_ticks,
            "steps": outcome.steps_taken,
            "tools": outcome.tools_used,
            "tool_actions": outcome.tool_actions,
            "memories_proposed": outcome.memories_proposed,
            "memories_written": outcome.memories_written,
            "outcome_summary": outcome.outcome_summary or "",
            "stop_reason": outcome.stop_reason or "",
            "errors": outcome.errors,
        }
        if outcome.metering:
            tick_end_data["metering"] = outcome.metering
        print(f"[tick-end] {json.dumps(tick_end_data, default=str)}", flush=True)

    # --- Log burst end ---
    total_errors = sum(len(o.errors) for o in outcomes)
    total_memories = sum(o.memories_written for o in outcomes)
    total_inbox = sum(
        sum(1 for t in o.tools_used if t.startswith("creator_inbox"))
        for o in outcomes
    )

    cost_str = f"${burst_metering.cost.total_cost:.4f}"
    est_tag = " (estimated)" if burst_metering.usage.is_estimated else ""
    print(
        f"[burst] Done | ticks={len(outcomes)} errors={total_errors} "
        f"memories_written={total_memories} inbox_sent={total_inbox} "
        f"tokens={burst_metering.usage.total_tokens} cost={cost_str}{est_tag}"
    )

    return outcomes
