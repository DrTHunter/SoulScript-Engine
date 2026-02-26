"""Offline tests for the Boundary / Capability Request system.

Run from project root:
    python -m tests.test_boundary

No LLM connection required.
"""

import json
import os
import sys
import tempfile
import shutil

# ── ensure project root is on path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.policy.boundary import (
    BoundaryEvent,
    BoundaryLogger,
    build_denial,
    classify_risk,
)

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


# ==================================================================
# 1. Risk classification
# ==================================================================

def test_risk_classification():
    print("\n=== Risk Classification ===")

    check("memory.recall is low", classify_risk("memory.recall") == "low")
    check("memory.add is med", classify_risk("memory.add") == "med")
    check("web.search is high", classify_risk("web.search") == "high")
    check("email.send is high", classify_risk("email.send") == "high")
    check("filesystem.write is high", classify_risk("filesystem.write") == "high")
    check("shell.exec is high", classify_risk("shell.exec") == "high")
    check("echo is low", classify_risk("echo") == "low")
    check("unknown defaults to med", classify_risk("quantum.teleport") == "med")
    # Base-name fallback: "web.something_new" -> checks "web" -> high
    check("web.foo falls back to web -> high", classify_risk("web.foo") == "high")


# ==================================================================
# 2. build_denial()
# ==================================================================

def test_build_denial():
    print("\n=== build_denial ===")

    denial_json, event = build_denial(
        tool_name="web.search",
        profile="orion",
        reason="Not allowed in this mode.",
        tick_index=3,
        tool_args={"query": "latest news"},
    )

    # Check denial payload
    payload = json.loads(denial_json)
    check("payload has TOOL_NOT_ALLOWED",
          payload.get("error") == "TOOL_NOT_ALLOWED")
    check("payload tool == web.search",
          payload.get("tool") == "web.search")
    check("payload has how_to_enable",
          "allowed_tools" in payload.get("how_to_enable", ""))

    # Check event
    check("event type", event.type == "boundary_request")
    check("event profile", event.profile == "orion")
    check("event tick_index", event.tick_index == 3)
    check("event requested_capability", event.requested_capability == "web.search")
    check("event reason", event.reason == "Not allowed in this mode.")
    check("event risk_level is high", event.risk_level == "high")
    check("event timestamp present", len(event.timestamp) > 0)
    check("event tool_args preserved", event.tool_args == {"query": "latest news"})
    check("event denial_payload matches", event.denial_payload == payload)
    check("event proposed_limits has rate_limit",
          "rate_limit" in event.proposed_limits)


def test_build_denial_default_reason():
    print("\n=== build_denial default reason ===")

    denial_json, event = build_denial(
        tool_name="filesystem.write",
        profile="elysia",
    )
    check("default reason mentions tool name",
          "filesystem.write" in event.reason)
    check("default reason mentions profile",
          "elysia" in event.reason)


# ==================================================================
# 3. BoundaryLogger (append-only JSONL)
# ==================================================================

def test_boundary_logger():
    print("\n=== BoundaryLogger ===")

    tmpdir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmpdir, "boundary_events.jsonl")
        logger = BoundaryLogger(path)

        # Append two events
        _, event1 = build_denial("web.search", "orion", tick_index=0)
        _, event2 = build_denial("email.send", "orion", tick_index=1)
        logger.append(event1)
        logger.append(event2)

        # File exists
        check("file created", os.path.exists(path))

        # Read back
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        check("2 lines written", len(lines) == 2)

        # Parse first line
        line1 = json.loads(lines[0])
        check("line1 type", line1["type"] == "boundary_request")
        check("line1 profile", line1["profile"] == "orion")
        check("line1 requested_capability", line1["requested_capability"] == "web.search")
        check("line1 risk_level", line1["risk_level"] == "high")
        check("line1 timestamp", len(line1["timestamp"]) > 0)
        check("line1 denial_payload present", "error" in line1["denial_payload"])

        # Parse second line
        line2 = json.loads(lines[1])
        check("line2 requested_capability", line2["requested_capability"] == "email.send")
        check("line2 risk_level high", line2["risk_level"] == "high")
        check("line2 proposed_limits has require_approval",
              line2["proposed_limits"].get("require_approval") is True)

        # read_all helper
        events = logger.read_all()
        check("read_all returns 2 events", len(events) == 2)
        check("read_all[0] is BoundaryEvent",
              isinstance(events[0], BoundaryEvent))
    finally:
        shutil.rmtree(tmpdir)


def test_logger_empty_file():
    print("\n=== BoundaryLogger: empty file ===")

    tmpdir = tempfile.mkdtemp()
    try:
        logger = BoundaryLogger(os.path.join(tmpdir, "empty.jsonl"))
        events = logger.read_all()
        check("read_all on missing file returns []", events == [])
    finally:
        shutil.rmtree(tmpdir)


def test_boundary_event_to_dict():
    """BoundaryEvent serialises all required fields."""
    print("\n=== BoundaryEvent.to_dict ===")

    event = BoundaryEvent(
        type="boundary_request",
        profile="orion",
        tick_index=5,
        requested_capability="shell.exec",
        reason="Blocked.",
        risk_level="high",
        proposed_limits={"allowed_commands": [], "require_approval": True},
        timestamp="2026-02-13T18:00:00Z",
        tool_args={"command": "rm -rf /"},
        denial_payload={"error": "TOOL_NOT_ALLOWED", "tool": "shell.exec"},
    )

    d = event.to_dict()
    required_keys = {
        "type", "profile", "tick_index", "requested_capability",
        "reason", "risk_level", "proposed_limits", "timestamp",
        "tool_args", "denial_payload",
    }
    check("all required keys present", required_keys.issubset(d.keys()),
          f"missing: {required_keys - set(d.keys())}")
    check("tick_index == 5", d["tick_index"] == 5)
    check("risk_level high", d["risk_level"] == "high")


# ==================================================================
# Main
# ==================================================================

if __name__ == "__main__":
    test_risk_classification()
    test_build_denial()
    test_build_denial_default_reason()
    test_boundary_logger()
    test_logger_empty_file()
    test_boundary_event_to_dict()

    print(f"\n{'='*50}")
    print(f"  PASSED: {PASS}   FAILED: {FAIL}   TOTAL: {PASS + FAIL}")
    print(f"{'='*50}")

    sys.exit(1 if FAIL > 0 else 0)
