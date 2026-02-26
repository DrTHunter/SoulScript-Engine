"""Offline tests for the ToolRequestWriter and registry get_description.

Run from project root:
    python -m tests.test_tool_requests

No LLM connection required.
"""

import os
import sys
import tempfile
import shutil

# -- ensure project root is on path --
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.tool_request_writer import ToolRequestWriter
from src.tools.registry import ToolRegistry

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
        path = os.path.join(tmp, "tool_requests.md")
        ToolRequestWriter(path)
        content = _read(path)
        check("file created", os.path.isfile(path))
        check("header present", content.startswith("# Tool Request Log"))
    finally:
        shutil.rmtree(tmp)


def test_header_not_duplicated():
    print("\n-- test_header_not_duplicated --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        ToolRequestWriter(path)
        ToolRequestWriter(path)  # second instantiation
        content = _read(path)
        count = content.count("# Tool Request Log")
        check("header appears exactly once", count == 1, f"found {count}")
    finally:
        shutil.rmtree(tmp)


def test_single_request_all_fields():
    print("\n-- test_single_request_all_fields --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Read, write, search durable memories.",
            arguments={"action": "add", "scope": "shared", "text": "hello"},
            context="Storing identity anchor for continuity.",
        )
        content = _read(path)
        check("agent in heading", "| orion |" in content)
        check("tool in heading", "| memory" in content)
        check("description present", "**Description:** Read, write, search durable memories." in content)
        check("action extracted", "**Action:** add" in content)
        check("args present", "scope=shared" in content)
        check("context present", "**Context:** Storing identity anchor" in content)
        check("separator present", "---" in content)
    finally:
        shutil.rmtree(tmp)


def test_action_extracted_from_args():
    print("\n-- test_action_extracted_from_args --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Memory tool.",
            arguments={"action": "recall", "scope": "shared", "limit": 10},
            context="Reviewing memories.",
        )
        content = _read(path)
        check("action on its own", "**Action:** recall" in content)
        check("action not in args", "action=" not in content)
        check("other args present", "scope=shared" in content)
        check("limit present", "limit=10" in content)
    finally:
        shutil.rmtree(tmp)


def test_no_action_key():
    print("\n-- test_no_action_key --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="elysia",
            tool_name="echo",
            description="Echoes back the message.",
            arguments={"message": "hello"},
            context="Testing.",
        )
        content = _read(path)
        check("no Action label", "**Action:**" not in content)
        check("Args present", "**Args:** message=hello" in content)
    finally:
        shutil.rmtree(tmp)


def test_empty_context():
    print("\n-- test_empty_context --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Memory tool.",
            arguments={"action": "recall"},
            context="",
        )
        content = _read(path)
        check("fallback context", "**Context:** No context provided." in content)
    finally:
        shutil.rmtree(tmp)


def test_long_context_truncated():
    print("\n-- test_long_context_truncated --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        long_text = "A" * 500
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Memory tool.",
            arguments={"action": "add"},
            context=long_text,
        )
        content = _read(path)
        check("context truncated", "..." in content)
        # The context line should have at most 300 chars of the original + "..."
        ctx_line = [ln for ln in content.splitlines() if ln.startswith("**Context:**")][0]
        # "**Context:** " is 13 chars, then 300 A's + "..."
        check("truncated length correct", len(ctx_line) <= 13 + 300 + 3 + 5,
              f"len={len(ctx_line)}")
    finally:
        shutil.rmtree(tmp)


def test_multiple_agents_appended():
    print("\n-- test_multiple_agents_appended --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Memory tool.",
            arguments={"action": "add"},
            context="First request.",
        )
        w.log_request(
            agent="elysia",
            tool_name="echo",
            description="Echo tool.",
            arguments={"message": "hi"},
            context="Second request.",
        )
        content = _read(path)
        check("orion entry present", "| orion |" in content)
        check("elysia entry present", "| elysia |" in content)
        check("two separators", content.count("---") >= 2)
        check("first context", "First request." in content)
        check("second context", "Second request." in content)
    finally:
        shutil.rmtree(tmp)


def test_empty_arguments():
    print("\n-- test_empty_arguments --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="echo",
            description="Echo tool.",
            arguments={},
            context="No args test.",
        )
        content = _read(path)
        check("no Args line", "**Args:**" not in content)
        check("no Action line", "**Action:**" not in content)
    finally:
        shutil.rmtree(tmp)


def test_long_arg_value_truncated():
    print("\n-- test_long_arg_value_truncated --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Memory tool.",
            arguments={"action": "add", "text": "X" * 200},
            context="Long value.",
        )
        content = _read(path)
        check("long value truncated", "..." in content)
    finally:
        shutil.rmtree(tmp)


def test_registry_get_description():
    print("\n-- test_registry_get_description --")
    reg = ToolRegistry(allowed=["echo", "memory"], profile="test")
    desc = reg.get_description("echo")
    check("echo description returned", "echo" in desc.lower() or len(desc) > 5,
          f"got: {desc}")
    desc_mem = reg.get_description("memory")
    check("memory description returned", len(desc_mem) > 10,
          f"got: {desc_mem}")


def test_registry_get_description_unknown():
    print("\n-- test_registry_get_description_unknown --")
    reg = ToolRegistry(allowed=["echo"], profile="test")
    desc = reg.get_description("nonexistent_tool")
    check("unknown tool fallback", desc == "Unknown tool.", f"got: {desc}")


def test_whitespace_formatting():
    """Verify blank lines exist around content for readability."""
    print("\n-- test_whitespace_formatting --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "tool_requests.md")
        w = ToolRequestWriter(path)
        w.log_request(
            agent="orion",
            tool_name="memory",
            description="Memory tool.",
            arguments={"action": "add"},
            context="My reasoning here.",
        )
        content = _read(path)
        check("blank line before context",
              "\n\n**Context:**" in content)
        check("blank line after context",
              "My reasoning here.\n\n" in content)
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

if __name__ == "__main__":
    test_creates_file_with_header()
    test_header_not_duplicated()
    test_single_request_all_fields()
    test_action_extracted_from_args()
    test_no_action_key()
    test_empty_context()
    test_long_context_truncated()
    test_multiple_agents_appended()
    test_empty_arguments()
    test_long_arg_value_truncated()
    test_registry_get_description()
    test_registry_get_description_unknown()
    test_whitespace_formatting()

    print(f"\n{'='*40}")
    print(f"  PASS: {PASS}   FAIL: {FAIL}")
    print(f"{'='*40}")
    sys.exit(1 if FAIL else 0)
