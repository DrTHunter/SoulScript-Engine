"""Offline tests for all tools, router, policy, and storage.

Run from project root:
    python -m tests.test_tools

No LLM connection required — exercises everything except the live chat call.
"""

import json
import os
import sys
import tempfile
import shutil

# ── ensure project root is on path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.registry import ToolRegistry
from src.runtime_policy import RuntimePolicy
from src.data_paths import task_inbox_path

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


def _dispatch(reg, name, arguments):
    """Helper: call dispatch and return only the result string."""
    result, _event = reg.dispatch(name, arguments)
    return result


# ─────────────────────────────────────────────
# 1. Echo tool
# ─────────────────────────────────────────────
def test_echo():
    print("\n=== Echo Tool ===")
    reg = ToolRegistry(["echo"])

    defs = reg.get_definitions()
    check("echo definition exists", len(defs) == 1 and defs[0]["name"] == "echo")

    result = _dispatch(reg, "echo", {"message": "hello world"})
    check("echo returns message", result == "hello world", f"got: {result!r}")

    # Disallowed tool now returns denial payload instead of raising
    result, event = reg.dispatch("task_inbox", {"action": "next"})
    denial = json.loads(result)
    check("echo-only blocks task_inbox",
          denial.get("error") == "TOOL_NOT_ALLOWED" and denial.get("tool") == "task_inbox",
          f"got: {result!r}")


# ─────────────────────────────────────────────
# 2. Task Inbox tool
# ─────────────────────────────────────────────
def test_task_inbox():
    print("\n=== Task Inbox Tool ===")
    # Use a temp data dir so we don't pollute real data
    import src.data_paths as dp
    import src.tools.task_inbox as ti
    orig_root = dp.DATA_ROOT
    tmp_dir = tempfile.mkdtemp()
    dp.DATA_ROOT = tmp_dir
    # Also update the cached path in the module
    ti._JSONL_PATH = os.path.join(tmp_dir, "shared", "task_inbox.jsonl")

    reg = ToolRegistry(["task_inbox"])

    try:
        # Add two tasks
        r1 = _dispatch(reg, "task_inbox", {"action": "add", "task": "Fix bug #101", "profile": "orion"})
        check("add task 1", "Task added" in r1, r1)

        r2 = _dispatch(reg, "task_inbox", {"action": "add", "task": "Write docs", "profile": "elysia"})
        check("add task 2", "Task added" in r2, r2)

        # Next with profile filter
        r3 = _dispatch(reg, "task_inbox", {"action": "next", "profile": "orion"})
        check("next orion -> TASK_FOUND", "TASK_FOUND" in r3 and "Fix bug #101" in r3, r3)

        # Next without profile -> should get elysia task
        r4 = _dispatch(reg, "task_inbox", {"action": "next"})
        check("next any -> elysia task", "TASK_FOUND" in r4 and "Write docs" in r4, r4)

        # Next when empty
        r5 = _dispatch(reg, "task_inbox", {"action": "next"})
        check("next empty -> NO_TASK", "NO_TASK" in r5, r5)

        # Invalid action
        r6 = _dispatch(reg, "task_inbox", {"action": "delete"})
        check("bad action -> Error", "Error" in r6, r6)

        # Invalid profile name
        r7 = _dispatch(reg, "task_inbox", {"action": "add", "task": "x", "profile": "../../etc"})
        check("path traversal blocked", "Error" in r7, r7)

        # Verify JSONL file has exactly 2 lines
        with open(ti._JSONL_PATH, "r") as f:
            lines = [l for l in f if l.strip()]
        check("JSONL has 2 entries", len(lines) == 2, f"got {len(lines)}")
        entry = json.loads(lines[0])
        check("first entry marked done", entry["status"] == "done")

    finally:
        dp.DATA_ROOT = orig_root
        ti._JSONL_PATH = task_inbox_path()  # re-resolve from restored root
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────
# 2b. Task Inbox: ack + dry_run
# ─────────────────────────────────────────────
def test_task_inbox_ack_dry_run():
    print("\n=== Task Inbox: Ack + Dry Run ===")
    import src.data_paths as dp
    import src.tools.task_inbox as ti
    orig_root = dp.DATA_ROOT
    tmp_dir = tempfile.mkdtemp()
    dp.DATA_ROOT = tmp_dir
    ti._JSONL_PATH = os.path.join(tmp_dir, "shared", "task_inbox.jsonl")

    reg = ToolRegistry(["task_inbox"])

    try:
        # Dry-run add — no file should be written
        r1 = _dispatch(reg, "task_inbox", {"action": "add", "task": "Test dry", "dry_run": True})
        check("dry_run add returns DRY_RUN", "[DRY_RUN]" in r1, r1)
        check("dry_run add no file", not os.path.exists(ti._JSONL_PATH))

        # Real add
        r2 = _dispatch(reg, "task_inbox", {"action": "add", "task": "Real task"})
        check("real add", "Task added" in r2, r2)
        task_id = r2.split("id=")[1].split(")")[0]

        # Dry-run next
        r3 = _dispatch(reg, "task_inbox", {"action": "next", "dry_run": True})
        check("dry_run next returns DRY_RUN", "[DRY_RUN]" in r3, r3)
        # Task should still be pending
        entries = ti._read_all()
        check("task still pending after dry_run next", entries[0]["status"] == "pending")

        # Ack with missing task_id
        r4 = _dispatch(reg, "task_inbox", {"action": "ack"})
        check("ack missing id -> Error", "Error" in r4, r4)

        # Ack nonexistent task
        r5 = _dispatch(reg, "task_inbox", {"action": "ack", "task_id": "doesnotexist"})
        check("ack bad id -> not found", "not found" in r5, r5)

        # Dry-run ack
        r6 = _dispatch(reg, "task_inbox", {"action": "ack", "task_id": task_id, "dry_run": True})
        check("dry_run ack returns DRY_RUN", "[DRY_RUN]" in r6, r6)
        entries2 = ti._read_all()
        check("task still pending after dry_run ack", entries2[0]["status"] == "pending")

        # Real ack
        r7 = _dispatch(reg, "task_inbox", {"action": "ack", "task_id": task_id})
        check("ack success", "acknowledged" in r7, r7)
        entries3 = ti._read_all()
        check("task status is acknowledged", entries3[0]["status"] == "acknowledged")
        check("acked_at is set", "acked_at" in entries3[0])

        # Ack already acked
        r8 = _dispatch(reg, "task_inbox", {"action": "ack", "task_id": task_id})
        check("re-ack returns already", "already acknowledged" in r8, r8)

    finally:
        dp.DATA_ROOT = orig_root
        ti._JSONL_PATH = task_inbox_path()
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────
# 3. Continuation Update tool
# ─────────────────────────────────────────────
def test_continuation_update():
    print("\n=== Continuation Update Tool ===")
    import src.data_paths as dp
    orig_root = dp.DATA_ROOT
    tmp_dir = tempfile.mkdtemp()
    dp.DATA_ROOT = tmp_dir

    reg = ToolRegistry(["continuation_update"])

    try:
        # Append mode
        r1 = _dispatch(reg, "continuation_update", {
            "profile": "orion", "mode": "append", "content": "Started task A."
        })
        check("append succeeds", "Appended" in r1, r1)

        # Append again
        r2 = _dispatch(reg, "continuation_update", {
            "profile": "orion", "mode": "append", "content": "Finished task A."
        })
        check("second append succeeds", "Appended" in r2, r2)

        # Replace section (new)
        r3 = _dispatch(reg, "continuation_update", {
            "profile": "orion", "mode": "replace_section",
            "section": "Status", "content": "In progress."
        })
        check("replace_section adds new", "Added" in r3, r3)

        # Replace section (update)
        r4 = _dispatch(reg, "continuation_update", {
            "profile": "orion", "mode": "replace_section",
            "section": "Status", "content": "Complete."
        })
        check("replace_section updates", "Replaced" in r4, r4)

        # Verify file content
        path = os.path.join(tmp_dir, "orion", "continuation.md")
        with open(path, "r") as f:
            content = f.read()
        check("has 'Started task A'", "Started task A" in content)
        check("has 'Finished task A'", "Finished task A" in content)
        check("Status says Complete", "Complete." in content)
        check("old status replaced", content.count("## Status") == 1,
              f"found {content.count('## Status')} occurrences")

        # Different profile -> separate file
        r5 = _dispatch(reg, "continuation_update", {
            "profile": "elysia", "mode": "append", "content": "Hello from elysia."
        })
        elysia_path = os.path.join(tmp_dir, "elysia", "continuation.md")
        check("elysia file created", os.path.exists(elysia_path))

        # Path traversal blocked
        r6 = _dispatch(reg, "continuation_update", {
            "profile": "../escape", "mode": "append", "content": "bad"
        })
        check("path traversal blocked", "Error" in r6, r6)

        # Missing content
        r7 = _dispatch(reg, "continuation_update", {
            "profile": "orion", "mode": "append", "content": "  "
        })
        check("empty content blocked", "Error" in r7, r7)

    finally:
        dp.DATA_ROOT = orig_root
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────
# 4. Router (REMOVED — src.router was deleted)
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 5. Runtime Policy
# ─────────────────────────────────────────────
def test_policy():
    print("\n=== Runtime Policy ===")
    import time

    p = RuntimePolicy(max_iterations=3, max_wall_time_seconds=0.5)
    check("iter 0 ok", p.check(0, time.time()) is None)
    check("iter 2 ok", p.check(2, time.time()) is None)
    check("iter 3 blocked", "Max iterations" in (p.check(3, time.time()) or ""))

    old = time.time() - 1.0  # 1 second ago
    check("wall time exceeded", "Wall-time" in (p.check(0, old) or ""))

    stasis = RuntimePolicy(stasis_mode=True)
    check("stasis_mode flag", stasis.stasis_mode is True)

    stop_policy = RuntimePolicy(tool_failure_mode="stop")
    check("tool_failure_mode=stop", stop_policy.tool_failure_mode == "stop")


# ─────────────────────────────────────────────
# 6. State Store (REMOVED — src.storage.state_store was deleted)
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 7. Journal Store (REMOVED — src.storage.journal_store was deleted)
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 8. Registry allowlist enforcement
# ─────────────────────────────────────────────
def test_allowlist():
    print("\n=== Allowlist Enforcement ===")
    full = ToolRegistry(["echo", "task_inbox", "continuation_update"])
    check("full registry: 3 defs", len(full.get_definitions()) == 3)

    partial = ToolRegistry(["echo"])
    check("partial registry: 1 def", len(partial.get_definitions()) == 1)

    empty = ToolRegistry([])
    check("empty registry: 0 defs", len(empty.get_definitions()) == 0)

    result, event = empty.dispatch("echo", {"message": "test"})
    denial = json.loads(result)
    check("empty blocks echo",
          denial.get("error") == "TOOL_NOT_ALLOWED" and event is not None)


# ─────────────────────────────────────────────
# Run all
# ─────────────────────────────────────────────
if __name__ == "__main__":
    test_echo()
    test_task_inbox()
    test_task_inbox_ack_dry_run()
    test_continuation_update()
    test_policy()
    test_allowlist()

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)
    else:
        print("All tests passed.")
