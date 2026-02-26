"""Offline tests for the Burst Runner subsystem.

Run from project root:
    python -m tests.test_burst

No LLM connection required — uses a deterministic mock client.
"""

import json
import os
import sys
import tempfile
import shutil

# ── ensure project root is on path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm_client.base import LLMClient, LLMResponse
from src.memory.vault import MemoryVault
from src.runner.types import BurstConfig, StepAction, StepOutput, TickOutcome, ProposedMemory
from src.runner.tick import run_tick, _parse_step_output, build_system_prompt
from src.runner.burst import run_burst

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  {detail}")


# ------------------------------------------------------------------
# Mock LLM Client
# ------------------------------------------------------------------

class MockClient(LLMClient):
    """Deterministic LLM client that returns pre-scripted responses.

    ``responses`` is a list of raw JSON strings.  Each call to ``chat``
    pops the next response.  If exhausted, returns a stop action.
    """

    model = "mock-v1"

    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self._call_count = 0

    @property
    def call_count(self):
        return self._call_count

    def chat(self, messages, tools=None):
        self._call_count += 1
        if self._responses:
            content = self._responses.pop(0)
        else:
            content = json.dumps({
                "step_summary": "No more scripted responses.",
                "action": "stop",
                "tool_name": None,
                "tool_args": None,
                "proposed_memories": [],
                "stop_reason": "exhausted",
            })
        return LLMResponse(content=content, model=self.model)


class ErrorClient(LLMClient):
    """Client that always raises on chat()."""

    model = "error-v1"

    def chat(self, messages, tools=None):
        raise ConnectionError("Simulated LLM failure")


# ------------------------------------------------------------------
# Helper: make a profile dict (in-memory, no YAML file needed)
# ------------------------------------------------------------------

def _make_profile(name="orion"):
    return {
        "name": name,
        "provider": "openai",
        "model": "mock",
        "base_url": "http://localhost",
        "temperature": 0.0,
        "system_prompt": "",  # skip file load in tests
        "window_size": 50,
        "allowed_tools": ["memory"],
        "policy": {},
        "memory": {
            "enabled": True,
            "scopes": ["shared", name],
            "max_items": 20,
            "similarity_threshold": 0.85,
        },
    }


# ------------------------------------------------------------------
# Helper: JSON response builders
# ------------------------------------------------------------------

def _think(summary="Thinking..."):
    return json.dumps({
        "step_summary": summary,
        "action": "think",
        "tool_name": None,
        "tool_args": None,
        "proposed_memories": [],
        "stop_reason": None,
    })


def _stop(summary="Done.", reason="completed"):
    return json.dumps({
        "step_summary": summary,
        "action": "stop",
        "tool_name": None,
        "tool_args": None,
        "proposed_memories": [],
        "stop_reason": reason,
    })


def _tool_call(action, args=None, summary="Calling tool."):
    tool_args = {"action": action}
    if args:
        tool_args.update(args)
    return json.dumps({
        "step_summary": summary,
        "action": "tool",
        "tool_name": "memory",
        "tool_args": tool_args,
        "proposed_memories": [],
        "stop_reason": None,
    })


def _with_proposed(summary="Proposing memory.", text="Test memory", scope="orion", category="meta"):
    return json.dumps({
        "step_summary": summary,
        "action": "stop",
        "tool_name": None,
        "tool_args": None,
        "proposed_memories": [
            {"text": text, "scope": scope, "category": category, "tags": ["test"]},
        ],
        "stop_reason": "memory_proposed",
    })


# ==================================================================
# Test suites
# ==================================================================

def test_types():
    """Test data type construction and serialisation."""
    print("\n=== Types ===")

    # BurstConfig defaults
    cfg = BurstConfig(profile="orion")
    check("config defaults", cfg.burst_ticks == 15 and cfg.max_steps_per_tick == 3)
    check("config tool_name", cfg.tool_name() == "memory")
    check("config max_tool_calls default", cfg.max_tool_calls_per_tick == 2)

    # StepOutput from_dict
    step = StepOutput.from_dict({
        "step_summary": "test",
        "action": "tool",
        "tool_name": "memory",
        "tool_args": {"action": "recall"},
        "proposed_memories": [{"text": "hi", "scope": "shared", "category": "meta"}],
        "stop_reason": None,
    })
    check("step action parsed", step.action == StepAction.TOOL)
    check("step proposed count", len(step.proposed_memories) == 1)

    # StepOutput unknown action falls back to THINK
    step2 = StepOutput.from_dict({"action": "INVALID"})
    check("step unknown action -> think", step2.action == StepAction.THINK)

    # TickOutcome serialisation
    tic = TickOutcome(tick_index=3, steps_taken=2, tools_used=["memory.recall"])
    d = tic.to_dict()
    check("tick_outcome to_dict", d["tick_index"] == 3 and d["tools_used"] == ["memory.recall"])

    # ProposedMemory roundtrip
    pm = ProposedMemory(text="hello", scope="shared", category="bio", tags=["a"])
    d2 = pm.to_dict()
    pm2 = ProposedMemory.from_dict(d2)
    check("proposed_memory roundtrip", pm2.text == "hello" and pm2.tags == ["a"])


def test_parse_step_output():
    """Test JSON parsing with various model output formats."""
    print("\n=== Parse Step Output ===")

    # Clean JSON
    s1 = _parse_step_output('{"step_summary":"ok","action":"think","tool_name":null,'
                            '"tool_args":null,"proposed_memories":[],"stop_reason":null}')
    check("clean json", s1.action == StepAction.THINK and s1.step_summary == "ok")

    # Wrapped in markdown fences
    s2 = _parse_step_output('```json\n{"step_summary":"fenced","action":"stop",'
                            '"stop_reason":"done"}\n```')
    check("fenced json", s2.action == StepAction.STOP and s2.step_summary == "fenced")

    # Invalid JSON — fallback to think
    s3 = _parse_step_output("I'm not sure what to do here.")
    check("invalid json fallback", s3.action == StepAction.THINK)
    check("invalid json captures text", "not sure" in s3.step_summary)


def test_tick_runs_exactly_max_steps():
    """Tick runs up to max_steps_per_tick model calls, then stops."""
    print("\n=== Tick: Exact Step Count ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=3)

    # 3 think responses — should exhaust all 3 steps
    client = MockClient([_think("step0"), _think("step1"), _think("step2")])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0, stimulus="test")

        check("steps_taken == 3", outcome.steps_taken == 3, f"got {outcome.steps_taken}")
        # 3 model calls for steps + context messages between (think prompts add user msgs)
        # The client should have been called exactly 3 times
        check("llm called 3 times", client.call_count == 3, f"got {client.call_count}")
    finally:
        shutil.rmtree(tmpdir)


def test_tick_stops_early():
    """Tick ends before max_steps when model outputs stop action."""
    print("\n=== Tick: Early Stop ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=3)

    client = MockClient([_think("planning"), _stop("all done", "finished")])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("steps_taken == 2", outcome.steps_taken == 2)
        check("stop_reason set", outcome.stop_reason == "finished")
    finally:
        shutil.rmtree(tmpdir)


def test_tick_max_tool_calls():
    """Tick enforces max 2 tool calls — third attempt is denied."""
    print("\n=== Tick: Max 2 Tool Calls ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=5)

    # Step 0: tool call (allowed), step 1: second tool call (allowed),
    # step 2: third tool call (denied), step 3: stop
    client = MockClient([
        _tool_call("recall", {"scope": "orion", "limit": 5}, "First tool call"),
        _tool_call("search", {"query": "test"}, "Second tool call (should be allowed)"),
        _tool_call("recall", {"scope": "shared", "limit": 3}, "Third tool call (should be blocked)"),
        _stop("Giving up.", "tool_denied"),
    ])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("tools_used has 2 entries", len(outcome.tools_used) == 2,
              f"got {outcome.tools_used}")
        check("first tool is memory.recall", outcome.tools_used[0] == "memory.recall",
              f"got {outcome.tools_used}")
        check("second tool is memory.search", outcome.tools_used[1] == "memory.search",
              f"got {outcome.tools_used}")
        check("has tool_denied error",
              any("tool call blocked" in e for e in outcome.errors),
              f"errors: {outcome.errors}")
    finally:
        shutil.rmtree(tmpdir)


def test_tick_disallowed_tool():
    """Tick rejects tool calls to tools not in the allowed set."""
    print("\n=== Tick: Disallowed Tool ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=3)

    # Try calling a tool named "filesystem" — not allowed
    bad_tool = json.dumps({
        "step_summary": "Trying forbidden tool",
        "action": "tool",
        "tool_name": "filesystem",
        "tool_args": {"path": "/etc/passwd"},
        "proposed_memories": [],
        "stop_reason": None,
    })
    client = MockClient([bad_tool, _stop("ok")])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("tools_used is empty (blocked)", outcome.tools_used == [])
        check("has not_allowed error",
              any("not in allowed tools" in e or "not allowed" in e for e in outcome.errors),
              f"errors: {outcome.errors}")
    finally:
        shutil.rmtree(tmpdir)


def test_tick_disallowed_memory_action():
    """Tick rejects memory actions not in the allowed_tools tuple."""
    print("\n=== Tick: Disallowed Memory Action ===")

    profile = _make_profile()
    # Override allowed_tools to only permit recall and search
    config = BurstConfig(
        profile="orion",
        max_steps_per_tick=3,
        allowed_tools=("memory.recall", "memory.search"),
    )

    client = MockClient([
        _tool_call("delete", {"memory_id": "abc123"}, "Trying to delete"),
        _stop("Blocked."),
    ])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("tools_used is empty", outcome.tools_used == [])
        check("has action_denied error",
              any("not in allowed_tools" in e for e in outcome.errors),
              f"errors: {outcome.errors}")
    finally:
        shutil.rmtree(tmpdir)


def test_tick_proposed_memories_flushed():
    """Proposed memories are written through the vault at end of tick."""
    print("\n=== Tick: Memory Flush ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=2)

    client = MockClient([
        _with_proposed("Proposing a memory", text="Orion likes unit tests", scope="orion", category="preference"),
    ])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("memories_proposed == 1", outcome.memories_proposed == 1)
        check("memories_written == 1", outcome.memories_written == 1,
              f"got {outcome.memories_written}, errors: {outcome.errors}")

        # Verify it's actually in the vault
        stored = vault.recall_memories(scope="orion")
        check("memory in vault", len(stored) >= 1 and "unit tests" in stored[0].text,
              f"stored: {[m.text for m in stored]}")
    finally:
        shutil.rmtree(tmpdir)


def test_tick_llm_error_captured():
    """LLM errors are caught and recorded, not raised."""
    print("\n=== Tick: LLM Error ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=3)
    client = ErrorClient()

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("has llm_error", any("llm_error" in e for e in outcome.errors))
        check("steps_taken == 0", outcome.steps_taken == 0)
    finally:
        shutil.rmtree(tmpdir)


def test_burst_runs_n_ticks():
    """Burst runner executes exactly N ticks."""
    print("\n=== Burst: N Ticks ===")

    # We need to use run_burst with injected dependencies.
    # Since run_burst loads the profile from YAML, we test via run_tick loop.
    profile = _make_profile()
    config = BurstConfig(profile="orion", burst_ticks=5, max_steps_per_tick=1)

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))

        outcomes = []
        for i in range(config.burst_ticks):
            client = MockClient([_stop(f"Tick {i} done", "auto")])
            outcome = run_tick(profile, client, vault, config, tick_index=i)
            outcomes.append(outcome)

        check("ran exactly 5 ticks", len(outcomes) == 5)
        check("tick indices correct",
              [o.tick_index for o in outcomes] == [0, 1, 2, 3, 4])
    finally:
        shutil.rmtree(tmpdir)


def test_burst_continues_after_exception():
    """Burst continues to next tick even if a tick raises an exception."""
    print("\n=== Burst: Continue After Exception ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", burst_ticks=3, max_steps_per_tick=1)

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))

        outcomes = []
        for i in range(config.burst_ticks):
            if i == 1:
                # Tick 1 uses the error client
                client = ErrorClient()
            else:
                client = MockClient([_stop(f"Tick {i} ok")])

            outcome = run_tick(profile, client, vault, config, tick_index=i)
            outcomes.append(outcome)

        check("all 3 ticks ran", len(outcomes) == 3)
        check("tick 0 ok", len(outcomes[0].errors) == 0)
        check("tick 1 has error", len(outcomes[1].errors) > 0)
        check("tick 2 ok (continued)", len(outcomes[2].errors) == 0)
    finally:
        shutil.rmtree(tmpdir)


def test_tick_tool_call_executes():
    """A valid tool call (memory.recall) actually executes and returns data."""
    print("\n=== Tick: Tool Execution ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=3)

    tmpdir = tempfile.mkdtemp()
    try:
        # Seed the vault with a memory so recall has something to return
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        vault.add_memory("Orion prefers dark themes", "orion", "preference", source="manual")

        # Step 0: recall, step 1: stop (after seeing tool result)
        client = MockClient([
            _tool_call("recall", {"scope": "orion", "limit": 5}, "Recalling memories"),
            _stop("Found preferences.", "recall_complete"),
        ])

        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("tools_used includes memory.recall", "memory.recall" in outcome.tools_used)
        check("no errors", len(outcome.errors) == 0, f"errors: {outcome.errors}")
        check("steps_taken == 2", outcome.steps_taken == 2)
    finally:
        shutil.rmtree(tmpdir)


def test_system_prompt_assembly():
    """System prompt includes expected sections."""
    print("\n=== System Prompt Assembly ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=3)

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        prompt = build_system_prompt(profile, vault, config, tick_index=5, stimulus="test stimulus")

        check("has step protocol", "Burst-Mode Step Protocol" in prompt)
        check("has tick context", "tick_index: 5" in prompt)
        check("has burst_ticks", "burst_ticks: 15" in prompt)
        check("has stimulus", "test stimulus" in prompt)
        check("has max_steps", "3 steps" in prompt)
        check("has max_tools", "2 tool calls" in prompt)
    finally:
        shutil.rmtree(tmpdir)


def test_proposed_memory_pii_blocked():
    """Proposed memories with PII are blocked by the vault."""
    print("\n=== Tick: PII Blocked ===")

    profile = _make_profile()
    config = BurstConfig(profile="orion", max_steps_per_tick=1)

    # Propose a memory containing a fake SSN
    pii_memory = json.dumps({
        "step_summary": "Storing sensitive data",
        "action": "stop",
        "tool_name": None,
        "tool_args": None,
        "proposed_memories": [
            {"text": "User SSN is 123-45-6789", "scope": "orion", "category": "bio", "tags": []},
        ],
        "stop_reason": "done",
    })
    client = MockClient([pii_memory])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))
        outcome = run_tick(profile, client, vault, config, tick_index=0)

        check("memories_proposed == 1", outcome.memories_proposed == 1)
        check("memories_written == 0 (PII blocked)", outcome.memories_written == 0,
              f"got {outcome.memories_written}")
        check("has pii error",
              any("PII" in e or "pii" in e.lower() for e in outcome.errors),
              f"errors: {outcome.errors}")
    finally:
        shutil.rmtree(tmpdir)


# ------------------------------------------------------------------
# Task inbox burst gating tests
# ------------------------------------------------------------------

def test_tick_task_inbox_gating():
    """Task inbox in burst: allowlist, 1-per-tick cap, dry_run."""
    print("\n=== Tick: Task Inbox Burst Gating ===")
    profile = _make_profile()

    # Config WITHOUT task_inbox allowed
    config_no_task = BurstConfig(
        profile="orion",
        max_steps_per_tick=3,
        max_tool_calls_per_tick=3,
        allowed_tools=(
            "memory.recall", "memory.search", "memory.add",
        ),
    )

    # Try to call task_inbox - should be denied (not in allowed_tools)
    add_step = json.dumps({
        "step_summary": "Adding a task",
        "action": "tool",
        "tool_name": "task_inbox",
        "tool_args": {"action": "add", "task": "Hello", "profile": "orion"},
        "proposed_memories": [],
        "stop_reason": None,
    })
    stop = _stop("done")
    client = MockClient([add_step, stop])

    tmpdir = tempfile.mkdtemp()
    try:
        vault = MemoryVault(os.path.join(tmpdir, "vault.jsonl"))

        # Set up task_inbox temp path
        import src.data_paths as dp
        import src.tools.task_inbox as ti
        orig_root = dp.DATA_ROOT
        dp.DATA_ROOT = tmpdir
        ti._JSONL_PATH = os.path.join(tmpdir, "shared", "task_inbox.jsonl")

        outcome = run_tick(profile, client, vault, config_no_task, tick_index=0)
        check("task_inbox denied when not allowed",
              any("denied" in e for e in outcome.errors),
              f"errors: {outcome.errors}")
        check("no tools used on denial", "task_inbox.add" not in outcome.tools_used)

        # Config WITH task_inbox allowed
        config_with_task = BurstConfig(
            profile="orion",
            max_steps_per_tick=4,
            max_tool_calls_per_tick=4,
            allowed_tools=(
                "memory.recall", "memory.search", "memory.add",
                "task_inbox.add", "task_inbox.next", "task_inbox.ack",
            ),
        )

        # Two task_inbox calls in one tick — second should be denied (1-per-tick)
        add1 = json.dumps({
            "step_summary": "Adding task 1",
            "action": "tool",
            "tool_name": "task_inbox",
            "tool_args": {"action": "add", "task": "First task"},
            "proposed_memories": [],
            "stop_reason": None,
        })
        add2 = json.dumps({
            "step_summary": "Adding task 2",
            "action": "tool",
            "tool_name": "task_inbox",
            "tool_args": {"action": "add", "task": "Second task"},
            "proposed_memories": [],
            "stop_reason": None,
        })
        stop2 = _stop("done after tasks")
        client2 = MockClient([add1, add2, stop2])
        vault2 = MemoryVault(os.path.join(tmpdir, "vault2.jsonl"))

        outcome2 = run_tick(profile, client2, vault2, config_with_task, tick_index=1)
        check("first task_inbox call allowed", "task_inbox.add" in outcome2.tools_used)
        check("second task_inbox call denied (1/tick)",
              any("task_inbox_denied" in e for e in outcome2.errors),
              f"errors: {outcome2.errors}")

        # Dry-run: task_inbox add with dry_run=true
        dry_add = json.dumps({
            "step_summary": "Dry run add",
            "action": "tool",
            "tool_name": "task_inbox",
            "tool_args": {"action": "add", "task": "Dry task", "dry_run": True},
            "proposed_memories": [],
            "stop_reason": None,
        })
        stop3 = _stop("dry run done")
        client3 = MockClient([dry_add, stop3])
        vault3 = MemoryVault(os.path.join(tmpdir, "vault3.jsonl"))

        outcome3 = run_tick(profile, client3, vault3, config_with_task, tick_index=2)
        check("dry_run task_inbox call succeeds", "task_inbox.add" in outcome3.tools_used)
        check("no errors on dry_run", len(outcome3.errors) == 0,
              f"errors: {outcome3.errors}")

        dp.DATA_ROOT = orig_root
        ti._JSONL_PATH = dp.task_inbox_path()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ==================================================================
# Main
# ==================================================================

if __name__ == "__main__":
    test_types()
    test_parse_step_output()
    test_tick_runs_exactly_max_steps()
    test_tick_stops_early()
    test_tick_max_tool_calls()
    test_tick_disallowed_tool()
    test_tick_disallowed_memory_action()
    test_tick_proposed_memories_flushed()
    test_tick_llm_error_captured()
    test_burst_runs_n_ticks()
    test_burst_continues_after_exception()
    test_tick_tool_call_executes()
    test_system_prompt_assembly()
    test_proposed_memory_pii_blocked()
    test_tick_task_inbox_gating()

    print(f"\n{'='*50}")
    print(f"  PASSED: {PASS}   FAILED: {FAIL}   TOTAL: {PASS + FAIL}")
    print(f"{'='*50}")

    sys.exit(1 if FAIL > 0 else 0)
