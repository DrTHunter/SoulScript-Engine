"""Offline tests for the NarrativeWriter.

Run from project root:
    python -m tests.test_narrative

No LLM connection required.
"""

import os
import sys
import tempfile
import shutil

# ── ensure project root is on path ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.narrative_writer import NarrativeWriter

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


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_creates_file_with_header():
    print("\n-- test_creates_file_with_header --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        NarrativeWriter(path, "Orion")
        content = _read(path)
        check("file created", os.path.isfile(path))
        check("header present", content.startswith("# Orion - Narrative Log"))
    finally:
        shutil.rmtree(tmp)


def test_header_not_duplicated():
    print("\n-- test_header_not_duplicated --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        NarrativeWriter(path, "Orion")
        NarrativeWriter(path, "Orion")  # second instantiation
        content = _read(path)
        count = content.count("# Orion - Narrative Log")
        check("header appears exactly once", count == 1, f"found {count}")
    finally:
        shutil.rmtree(tmp)


def test_burst_session_full_flow():
    print("\n-- test_burst_session_full_flow --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:14:00Z", stimulus="hello orion")
        w.add_tick(0, "2026-02-13T18:14:10Z", "I am awakening and orienting.")
        w.add_tick(1, "2026-02-13T18:15:00Z", "Reflecting on my state.")
        w.end_burst_session(ticks_completed=2, memories_written=5)
        content = _read(path)
        check("burst session header", "## Burst Session | 2026-02-13 18:14 UTC" in content)
        check("stimulus blockquote", '> Stimulus: "hello orion"' in content)
        check("tick 0 header", "### Tick 0 | 18:14 UTC" in content)
        check("tick 0 narrative", "I am awakening and orienting." in content)
        check("tick 1 header", "### Tick 1 | 18:15 UTC" in content)
        check("tick 1 narrative", "Reflecting on my state." in content)
        check("session complete", "### Session Complete" in content)
        check("completion stats", "Completed 2 ticks. 5 memories written." in content)
    finally:
        shutil.rmtree(tmp)


def test_burst_session_no_stimulus():
    print("\n-- test_burst_session_no_stimulus --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:00:00Z", stimulus="")
        content = _read(path)
        check("no stimulus blockquote", "Stimulus" not in content)
        check("session header present", "## Burst Session" in content)
    finally:
        shutil.rmtree(tmp)


def test_auto_summary_replaced():
    print("\n-- test_auto_summary_replaced --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:00:00Z")
        w.add_tick(0, "2026-02-13T18:00:10Z",
                   "Tick 0 completed: 3 steps, tool=memory.add, memories=1/2")
        content = _read(path)
        check("auto-summary not in output",
              "3 steps, tool=memory.add" not in content)
        check("human placeholder present",
              "Tick ran to completion without an explicit narrative" in content)
    finally:
        shutil.rmtree(tmp)


def test_error_summary_replaced():
    print("\n-- test_error_summary_replaced --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:00:00Z")
        w.add_tick(2, "2026-02-13T18:00:10Z",
                   "Tick 2 failed with unhandled exception: some error")
        content = _read(path)
        check("error summary not in output",
              "unhandled exception" not in content)
        check("error placeholder present",
              "Tick encountered an error and could not complete." in content)
    finally:
        shutil.rmtree(tmp)


def test_model_summary_preserved():
    print("\n-- test_model_summary_preserved --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:00:00Z")
        model_narrative = ("I'm orienting to the loop: confirming identity continuity, "
                           "checking boundaries, and reporting my internal state.")
        w.add_tick(0, "2026-02-13T18:00:10Z", model_narrative)
        content = _read(path)
        check("model narrative preserved", model_narrative in content)
        check("not replaced with placeholder",
              "without an explicit narrative" not in content)
    finally:
        shutil.rmtree(tmp)


def test_empty_outcome_summary():
    print("\n-- test_empty_outcome_summary --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:00:00Z")
        w.add_tick(0, "2026-02-13T18:00:10Z", "")
        content = _read(path)
        check("empty handled gracefully",
              "No narrative recorded for this tick." in content)
    finally:
        shutil.rmtree(tmp)


def test_interactive_session():
    print("\n-- test_interactive_session --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Elysia")
        w.add_interactive_session(
            "2026-02-12T18:29:00Z",
            "Agent engaged with user over 4 exchanges. Tools used: echo (2x).",
        )
        content = _read(path)
        check("file heading", "# Elysia - Narrative Log" in content)
        check("interactive header",
              "## Interactive Session | 2026-02-12 18:29 UTC" in content)
        check("narrative text",
              "Agent engaged with user over 4 exchanges." in content)
    finally:
        shutil.rmtree(tmp)


def test_multiple_sessions_appended():
    print("\n-- test_multiple_sessions_appended --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")

        # First burst session
        w.begin_burst_session("2026-02-13T10:00:00Z", stimulus="first run")
        w.add_tick(0, "2026-02-13T10:00:10Z", "First tick narrative.")
        w.end_burst_session(1, 3)

        # Interactive session
        w.add_interactive_session("2026-02-13T12:00:00Z", "User discussed testing.")

        # Second burst session
        w.begin_burst_session("2026-02-13T14:00:00Z", stimulus="second run")
        w.add_tick(0, "2026-02-13T14:00:10Z", "Second run tick narrative.")
        w.end_burst_session(1, 1)

        content = _read(path)
        check("two burst sessions",
              content.count("## Burst Session") == 2)
        check("one interactive session",
              content.count("## Interactive Session") == 1)
        check("three horizontal rules",
              content.count("---") == 3)
        check("first narrative present", "First tick narrative." in content)
        check("second narrative present", "Second run tick narrative." in content)
        check("interactive narrative present", "User discussed testing." in content)
    finally:
        shutil.rmtree(tmp)


# test_build_interactive_narrative — REMOVED (src.loop was deleted)


def test_separator_whitespace():
    """Verify blank lines exist around narrative text for readability."""
    print("\n-- test_separator_whitespace --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "test_narrative.md")
        w = NarrativeWriter(path, "Orion")
        w.begin_burst_session("2026-02-13T18:00:00Z")
        w.add_tick(0, "2026-02-13T18:00:10Z", "My narrative here.")
        content = _read(path)
        # Narrative should have a blank line above and below it
        check("blank line before narrative",
              "\n\nMy narrative here." in content)
        check("blank line after narrative",
              "My narrative here.\n\n" in content)
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

if __name__ == "__main__":
    test_creates_file_with_header()
    test_header_not_duplicated()
    test_burst_session_full_flow()
    test_burst_session_no_stimulus()
    test_auto_summary_replaced()
    test_error_summary_replaced()
    test_model_summary_preserved()
    test_empty_outcome_summary()
    test_interactive_session()
    test_multiple_sessions_appended()
    test_separator_whitespace()

    print(f"\n{'='*40}")
    print(f"  PASS: {PASS}   FAIL: {FAIL}")
    print(f"{'='*40}")
    sys.exit(1 if FAIL else 0)
