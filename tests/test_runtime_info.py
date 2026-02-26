"""Offline tests for the runtime_info tool.

Run from project root:
    python -m tests.test_runtime_info

Exercises: definition schema, context injection, redaction, policy snapshot,
stasis-mode field, registry integration, and API-key safety.
"""

import json
import os
import sys

# ── ensure project root is on path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.runtime_info_tool import RuntimeInfoTool
from src.tools.registry import ToolRegistry
from src.runtime_policy import RuntimePolicy

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


# ── Sample profile dicts used across tests ──

_ORION_PROFILE = {
    "name": "orion",
    "provider": "openai",
    "model": "gpt-5.2",
    "base_url": "https://api.openai.com/v1",
    "temperature": 0.7,
    "system_prompt": "orion.system.md",
    "window_size": 50,
    "allowed_tools": ["echo", "memory", "runtime_info"],
    "policy": {"max_iterations": 25, "stasis_mode": False},
    "memory": {"enabled": True, "scopes": ["shared", "orion"], "max_items": 20, "similarity_threshold": 0.85},
    "directives": {"enabled": True, "scopes": ["shared", "orion"], "max_sections": 5},
}

_LOCALHOST_PROFILE = {
    "name": "test_agent",
    "provider": "ollama",
    "model": "llama3",
    "base_url": "http://localhost:11434",
    "temperature": 0.5,
    "window_size": 30,
    "allowed_tools": ["runtime_info"],
    "memory": {},
    "directives": {},
}


# ─────────────────────────────────────────────
# 1. Definition
# ─────────────────────────────────────────────
def test_definition():
    print("\n=== RuntimeInfo Definition ===")
    defn = RuntimeInfoTool.definition()
    check("name is runtime_info", defn["name"] == "runtime_info")
    check("has description", "description" in defn and len(defn["description"]) > 0)
    check("has parameters", "parameters" in defn)


# ─────────────────────────────────────────────
# 2. Execute before set_context (defaults)
# ─────────────────────────────────────────────
def test_execute_defaults():
    print("\n=== RuntimeInfo Execute (defaults) ===")
    # Reset to blank state
    RuntimeInfoTool.reset()

    raw = RuntimeInfoTool.execute({})
    data = json.loads(raw)
    check("returns valid JSON", isinstance(data, dict))
    check("agent defaults to unknown", data.get("agent") == "unknown")
    check("policy is empty dict when None", data.get("policy") == {})
    check("diff is empty on first call", data.get("diff") == [])
    check("diff_count is 0", data.get("diff_count") == 0)


# ─────────────────────────────────────────────
# 3. Core fields after set_context
# ─────────────────────────────────────────────
def test_core_fields():
    print("\n=== RuntimeInfo Core Fields ===")
    RuntimeInfoTool.reset()
    policy = RuntimePolicy(max_iterations=25, stasis_mode=False, tool_failure_mode="continue")
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="interactive")

    data = json.loads(RuntimeInfoTool.execute({}))

    check("agent is orion", data["agent"] == "orion")
    check("provider is openai", data["provider"] == "openai")
    check("model is gpt-5.2", data["model"] == "gpt-5.2")
    check("temperature is 0.7", data["temperature"] == 0.7)
    check("window_size is 50", data["window_size"] == 50)


# ─────────────────────────────────────────────
# 4. base_url redaction
# ─────────────────────────────────────────────
def test_base_url_redaction():
    print("\n=== RuntimeInfo base_url Redaction ===")
    policy = RuntimePolicy()

    # OpenAI URL
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy)
    data = json.loads(RuntimeInfoTool.execute({}))
    check("openai host redacted", data["base_url_host"] == "api.openai.com",
          f"got: {data['base_url_host']!r}")

    # Localhost with port
    RuntimeInfoTool.set_context(_LOCALHOST_PROFILE, policy)
    data = json.loads(RuntimeInfoTool.execute({}))
    check("localhost host redacted", data["base_url_host"] == "localhost",
          f"got: {data['base_url_host']!r}")


# ─────────────────────────────────────────────
# 5. Execution mode
# ─────────────────────────────────────────────
def test_execution_mode():
    print("\n=== RuntimeInfo Execution Mode ===")
    policy = RuntimePolicy()

    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="interactive")
    data = json.loads(RuntimeInfoTool.execute({}))
    check("mode is interactive", data["execution_mode"] == "interactive")

    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="burst")
    data = json.loads(RuntimeInfoTool.execute({}))
    check("mode is burst", data["execution_mode"] == "burst")


# ─────────────────────────────────────────────
# 6. Policy snapshot
# ─────────────────────────────────────────────
def test_policy_snapshot():
    print("\n=== RuntimeInfo Policy Snapshot ===")
    policy = RuntimePolicy(
        max_iterations=10,
        max_wall_time_seconds=120.0,
        stasis_mode=True,
        tool_failure_mode="stop",
        self_refine_steps=3,
    )
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy)
    data = json.loads(RuntimeInfoTool.execute({}))
    ps = data["policy"]

    check("policy has all 5 fields", len(ps) == 5, f"got {len(ps)} fields: {list(ps.keys())}")
    check("max_iterations is 10", ps["max_iterations"] == 10)
    check("max_wall_time_seconds is 120", ps["max_wall_time_seconds"] == 120.0)
    check("stasis_mode is true", ps["stasis_mode"] is True)
    check("tool_failure_mode is stop", ps["tool_failure_mode"] == "stop")
    check("self_refine_steps is 3", ps["self_refine_steps"] == 3)


# ─────────────────────────────────────────────
# 7. Sub-config pass-through
# ─────────────────────────────────────────────
def test_sub_configs():
    print("\n=== RuntimeInfo Sub-Configs ===")
    policy = RuntimePolicy()
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy)
    data = json.loads(RuntimeInfoTool.execute({}))

    check("allowed_tools preserved", data["allowed_tools"] == ["echo", "memory", "runtime_info"])
    check("memory config preserved", data["memory"]["enabled"] is True)
    check("memory scopes preserved", data["memory"]["scopes"] == ["shared", "orion"])
    check("directives config preserved", data["directives"]["enabled"] is True)
    check("directives max_sections preserved", data["directives"]["max_sections"] == 5)


# ─────────────────────────────────────────────
# 8. No API key leakage
# ─────────────────────────────────────────────
def test_no_api_key():
    print("\n=== RuntimeInfo No API Key ===")
    policy = RuntimePolicy()
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy)
    raw = RuntimeInfoTool.execute({})
    check("no sk- in output", "sk-" not in raw)
    check("no api_key field", "api_key" not in raw)


# ─────────────────────────────────────────────
# 9. Registry integration
# ─────────────────────────────────────────────
def test_registry():
    print("\n=== RuntimeInfo Registry Integration ===")
    reg = ToolRegistry(["runtime_info"])

    defs = reg.get_definitions()
    check("registry returns definition", len(defs) == 1 and defs[0]["name"] == "runtime_info")

    # Set context so execute produces valid output
    policy = RuntimePolicy()
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy)

    result, event = reg.dispatch("runtime_info", {})
    data = json.loads(result)
    check("registry dispatch returns valid JSON", data["agent"] == "orion")
    check("no boundary event on success", event is None)


# ─────────────────────────────────────────────
# 10. Diff ritual (on-demand)
# ─────────────────────────────────────────────
def test_diff_ritual():
    print("\n=== RuntimeInfo Diff Ritual ===")
    RuntimeInfoTool.reset()
    policy = RuntimePolicy()
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="interactive")

    # First call — no previous snapshot, diff should be empty
    data1 = json.loads(RuntimeInfoTool.execute({}))
    check("first call diff empty", data1["diff"] == [])
    check("first call diff_count 0", data1["diff_count"] == 0)

    # Second call — same context, no changes
    data2 = json.loads(RuntimeInfoTool.execute({}))
    check("identical context diff empty", data2["diff"] == [])

    # Change context — execution_mode changes
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="burst")
    data3 = json.loads(RuntimeInfoTool.execute({}))
    check("mode change detected", data3["diff_count"] > 0)
    diff_fields = [d["field"] for d in data3["diff"]]
    check("execution_mode in diff", "execution_mode" in diff_fields)
    mode_diff = [d for d in data3["diff"] if d["field"] == "execution_mode"][0]
    check("old mode is interactive", '"interactive"' in mode_diff["old"])
    check("new mode is burst", '"burst"' in mode_diff["new"])

    # Change policy — should show up in diff
    new_policy = RuntimePolicy(max_iterations=99, stasis_mode=True)
    RuntimeInfoTool.set_context(_ORION_PROFILE, new_policy, execution_mode="burst")
    data4 = json.loads(RuntimeInfoTool.execute({}))
    diff_fields4 = [d["field"] for d in data4["diff"]]
    check("policy change detected", "policy" in diff_fields4)


# ─────────────────────────────────────────────
# 11. Required fields
# ─────────────────────────────────────────────
def test_required_fields():
    print("\n=== RuntimeInfo Required Fields ===")
    RuntimeInfoTool.reset()
    policy = RuntimePolicy()
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy)
    data = json.loads(RuntimeInfoTool.execute({}))

    for rf in RuntimeInfoTool.REQUIRED_FIELDS:
        check(f"required field '{rf}' present", rf in data,
              f"missing from snapshot keys: {list(data.keys())}")


# ─────────────────────────────────────────────
# 12. Burst config injection
# ─────────────────────────────────────────────
def test_burst_config():
    print("\n=== RuntimeInfo Burst Config ===")
    RuntimeInfoTool.reset()
    policy = RuntimePolicy()
    burst = {
        "tick_index": 3,
        "burst_ticks": 15,
        "max_steps_per_tick": 3,
        "max_tool_calls_per_tick": 2,
        "allowed_tools": ["memory.recall", "memory.add"],
    }
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="burst", burst_config=burst)
    data = json.loads(RuntimeInfoTool.execute({}))
    check("burst key present", "burst" in data)
    check("burst tick_index", data["burst"]["tick_index"] == 3)
    check("burst burst_ticks", data["burst"]["burst_ticks"] == 15)
    check("burst allowed_tools", data["burst"]["allowed_tools"] == ["memory.recall", "memory.add"])

    # Without burst config, no burst key
    RuntimeInfoTool.reset()
    RuntimeInfoTool.set_context(_ORION_PROFILE, policy, execution_mode="interactive")
    data2 = json.loads(RuntimeInfoTool.execute({}))
    check("no burst key in interactive", "burst" not in data2)


# ─────────────────────────────────────────────
# Run all
# ─────────────────────────────────────────────
if __name__ == "__main__":
    test_definition()
    test_execute_defaults()
    test_core_fields()
    test_base_url_redaction()
    test_execution_mode()
    test_policy_snapshot()
    test_sub_configs()
    test_no_api_key()
    test_registry()
    test_diff_ritual()
    test_required_fields()
    test_burst_config()

    total = PASS + FAIL
    print(f"\n{'='*50}")
    print(f"runtime_info: {PASS}/{total} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)
    print("All checks passed.")
