"""Offline tests for the Creator Inbox tool.

Run from project root:
    python -m tests.test_creator_inbox

No LLM connection required.
"""

import json
import os
import sys
import tempfile
import shutil

# ── ensure project root is on path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f" — {detail}"
        print(msg)


# ---------------------------------------------------------------------------
# Helpers — redirect module-level paths to temp dirs
# ---------------------------------------------------------------------------

_original_data_root = None
_tmp_dir = None


def _setup_temp():
    """Redirect data paths to a temp directory."""
    global _original_data_root, _tmp_dir
    import src.data_paths as dp
    _original_data_root = dp.DATA_ROOT
    _tmp_dir = tempfile.mkdtemp(prefix="test_creator_inbox_")
    dp.DATA_ROOT = _tmp_dir

    # Force re-evaluation of paths in creator_inbox module
    import src.tools.creator_inbox as ti
    ti._JSONL_PATH = dp.creator_inbox_path()
    ti._MD_PATH = os.path.join(_tmp_dir, "creator_inbox.md")


def _teardown_temp():
    """Restore original paths and clean up."""
    global _original_data_root, _tmp_dir
    import src.data_paths as dp
    dp.DATA_ROOT = _original_data_root

    import src.tools.creator_inbox as ti
    ti._JSONL_PATH = dp.creator_inbox_path()
    ti._MD_PATH = os.path.join(dp.DATA_ROOT, "creator_inbox.md")

    if _tmp_dir and os.path.exists(_tmp_dir):
        shutil.rmtree(_tmp_dir, ignore_errors=True)


def _send(**kwargs):
    """Shortcut to execute a send action."""
    from src.tools.creator_inbox import CreatorInboxTool
    args = {"action": "send"}
    args.update(kwargs)
    if "_from" not in args:
        args["_from"] = "orion"
    return CreatorInboxTool.execute(args)


def _read_jsonl():
    """Read all entries from the JSONL file."""
    import src.tools.creator_inbox as ti
    if not os.path.exists(ti._JSONL_PATH):
        return []
    entries = []
    with open(ti._JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _read_md():
    """Read the derived markdown file."""
    import src.tools.creator_inbox as ti
    if not os.path.exists(ti._MD_PATH):
        return ""
    with open(ti._MD_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ===========================================================================
# Test groups
# ===========================================================================

def test_definition():
    """Tool definition has expected structure."""
    print("\n--- definition ---")
    from src.tools.creator_inbox import CreatorInboxTool

    defn = CreatorInboxTool.definition()
    check("has name", defn.get("name") == "creator_inbox")
    check("has description", "operator" in defn.get("description", "").lower())
    check("has parameters", "properties" in defn.get("parameters", {}))
    props = defn["parameters"]["properties"]
    check("has action param", "action" in props)
    check("has type param", "type" in props)
    check("has subject param", "subject" in props)
    check("has body param", "body" in props)
    check("has needs_approval param", "needs_approval" in props)
    check("has priority param", "priority" in props)
    required = defn["parameters"].get("required", [])
    check("action required", "action" in required)
    check("type required", "type" in required)
    check("subject required", "subject" in required)
    check("body required", "body" in required)


def test_send_basic():
    """Basic send creates JSONL entry and returns confirmation."""
    print("\n--- send basic ---")
    _setup_temp()
    try:
        result = _send(
            type="message",
            subject="Hello operator",
            body="This is a test message from Orion.",
        )
        check("returns confirmation", "Message sent" in result)
        check("returns id", "id=" in result)

        entries = _read_jsonl()
        check("jsonl has one entry", len(entries) == 1)

        e = entries[0]
        check("has id field", len(e.get("id", "")) == 12)
        check("from is orion", e.get("from") == "orion")
        check("type is message", e.get("type") == "message")
        check("priority defaults normal", e.get("priority") == "normal")
        check("subject matches", e.get("subject") == "Hello operator")
        check("body matches", e.get("body") == "This is a test message from Orion.")
        check("needs_approval defaults false", e.get("needs_approval") is False)
        check("status is unread", e.get("status") == "unread")
        check("has created_at", "T" in e.get("created_at", ""))
    finally:
        _teardown_temp()


def test_send_all_types():
    """All four valid types are accepted."""
    print("\n--- send all types ---")
    _setup_temp()
    try:
        for t in ["message", "tool_request", "warning", "idea"]:
            result = _send(type=t, subject=f"Test {t}", body=f"Body for {t}")
            check(f"type '{t}' accepted", "Message sent" in result)

        entries = _read_jsonl()
        check("four entries total", len(entries) == 4)
        types = [e["type"] for e in entries]
        check("all types present", set(types) == {"message", "tool_request", "warning", "idea"})
    finally:
        _teardown_temp()


def test_send_all_priorities():
    """All four valid priorities are accepted."""
    print("\n--- send all priorities ---")
    _setup_temp()
    try:
        for p in ["low", "normal", "high", "urgent"]:
            result = _send(type="message", priority=p, subject=f"Pri {p}", body="body")
            check(f"priority '{p}' accepted", "Message sent" in result)
    finally:
        _teardown_temp()


def test_validation_errors():
    """Various validation failures return errors."""
    print("\n--- validation errors ---")
    _setup_temp()
    try:
        # Invalid type
        r = _send(type="bogus", subject="s", body="b")
        check("invalid type rejected", "Error" in r and "type" in r.lower())

        # Empty subject
        r = _send(type="message", subject="", body="b")
        check("empty subject rejected", "Error" in r and "subject" in r.lower())

        # Empty body
        r = _send(type="message", subject="s", body="")
        check("empty body rejected", "Error" in r and "body" in r.lower())

        # Subject too long
        r = _send(type="message", subject="x" * 121, body="b")
        check("long subject rejected", "Error" in r and "120" in r)

        # Body too long
        r = _send(type="message", subject="s", body="x" * 2001)
        check("long body rejected", "Error" in r and "2000" in r)

        # Invalid priority
        r = _send(type="message", priority="critical", subject="s", body="b")
        check("invalid priority rejected", "Error" in r and "priority" in r.lower())

        # Unknown action
        from src.tools.creator_inbox import CreatorInboxTool
        r = CreatorInboxTool.execute({"action": "read"})
        check("unknown action rejected", "Error" in r and "read" in r)

        # No entries should have been written
        entries = _read_jsonl()
        check("no entries written for errors", len(entries) == 0)
    finally:
        _teardown_temp()


def test_needs_approval():
    """needs_approval flag persists correctly."""
    print("\n--- needs_approval ---")
    _setup_temp()
    try:
        _send(
            type="tool_request",
            subject="Request web access",
            body="I would like to use a web fetch tool.",
            needs_approval=True,
        )
        entries = _read_jsonl()
        check("needs_approval is true", entries[0].get("needs_approval") is True)

        _send(
            type="message",
            subject="Just a note",
            body="No approval needed.",
        )
        entries = _read_jsonl()
        check("needs_approval defaults false", entries[1].get("needs_approval") is False)
    finally:
        _teardown_temp()


def test_multi_agent():
    """Messages from multiple agents interleave correctly."""
    print("\n--- multi-agent ---")
    _setup_temp()
    try:
        _send(type="message", subject="From Orion", body="Orion here.", _from="orion")
        _send(type="idea", subject="From Elysia", body="Elysia here.", _from="elysia")
        _send(type="warning", subject="From Orion again", body="Warning.", _from="orion")

        entries = _read_jsonl()
        check("three entries", len(entries) == 3)
        check("first from orion", entries[0]["from"] == "orion")
        check("second from elysia", entries[1]["from"] == "elysia")
        check("third from orion", entries[2]["from"] == "orion")
    finally:
        _teardown_temp()


def test_derived_markdown():
    """The derived markdown file is created and populated."""
    print("\n--- derived markdown ---")
    _setup_temp()
    try:
        _send(
            type="tool_request",
            priority="high",
            subject="Need file write access",
            body="For saving analysis results.",
            needs_approval=True,
            _from="orion",
        )

        md = _read_md()
        check("md file has header", "# Creator Inbox" in md)
        check("md has separator", "---" in md)
        check("md has subject", "Need file write access" in md)
        check("md has body", "For saving analysis results." in md)
        check("md has HIGH tag", "[HIGH]" in md)
        check("md has NEEDS APPROVAL tag", "[NEEDS APPROVAL]" in md)
        check("md has id", "id:" in md)
        check("md has from", "orion" in md)
        check("md has type", "tool_request" in md)
    finally:
        _teardown_temp()


def test_md_normal_priority_no_tag():
    """Normal and low priority messages don't get priority tags in markdown."""
    print("\n--- md normal priority ---")
    _setup_temp()
    try:
        _send(type="message", priority="normal", subject="Normal msg", body="body")
        md = _read_md()
        check("no priority tag for normal", "[NORMAL]" not in md)
        check("no HIGH tag", "[HIGH]" not in md)
    finally:
        _teardown_temp()


def test_registry_integration():
    """Tool is registered and dispatchable."""
    print("\n--- registry integration ---")
    from src.tools.registry import ToolRegistry

    reg = ToolRegistry(allowed=["creator_inbox"], profile="test")
    check("registered", reg.is_registered("creator_inbox"))
    check("allowed", reg.is_allowed("creator_inbox"))

    defn = [d for d in reg.get_definitions() if d["name"] == "creator_inbox"]
    check("definition included", len(defn) == 1)

    desc = reg.get_description("creator_inbox")
    check("description not empty", len(desc) > 10)


def test_burst_config():
    """BurstConfig includes creator_inbox.send in allowed_tools."""
    print("\n--- burst config ---")
    from src.runner.types import BurstConfig

    cfg = BurstConfig(profile="test")
    check("creator_inbox.send in allowed_tools", "creator_inbox.send" in cfg.allowed_tools)
    check("allowed_tool_names includes creator_inbox", "creator_inbox" in cfg.allowed_tool_names())
    check("allowed_tool_names includes memory", "memory" in cfg.allowed_tool_names())


def test_concurrent_appends():
    """Two rapid sends don't corrupt the file."""
    print("\n--- concurrent appends ---")
    _setup_temp()
    try:
        for i in range(10):
            _send(type="message", subject=f"Msg {i}", body=f"Body {i}")

        entries = _read_jsonl()
        check("all 10 entries written", len(entries) == 10)

        # Verify each is valid JSON with expected fields
        all_valid = all(
            e.get("id") and e.get("subject") and e.get("body")
            for e in entries
        )
        check("all entries valid", all_valid)
    finally:
        _teardown_temp()


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    test_definition()
    test_send_basic()
    test_send_all_types()
    test_send_all_priorities()
    test_validation_errors()
    test_needs_approval()
    test_multi_agent()
    test_derived_markdown()
    test_md_normal_priority_no_tag()
    test_registry_integration()
    test_burst_config()
    test_concurrent_appends()

    total = PASS + FAIL
    print(f"\n{'=' * 50}")
    print(f"  PASSED: {PASS}   FAILED: {FAIL}   TOTAL: {total}")
    print(f"{'=' * 50}")

    if FAIL > 0:
        sys.exit(1)
