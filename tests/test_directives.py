"""Tests for the Directives system.

Run from project root:
    python -m tests.test_directives
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.directives.parser import parse_directive_file, DirectiveSection
from src.directives.store import DirectiveStore, score_section
from src.directives.injector import build_directives_block
from src.directives.manifest import generate_manifest, save_manifest, load_manifest, diff_manifest, audit_changes, _heading_to_id, _sha256
from src.tools.directives_tool import DirectivesTool

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


SAMPLE_SHARED = """<!-- Shared directives -->

## First Words Protocol
When greeting the user for the first time in a session, reference recent
context and acknowledge the user warmly.

## Project Context
The user is building a multi-agent runtime called agent-runtime.
Tech stack: Python 3.11, YAML profiles, JSONL storage.

## Communication Style
Be direct. Avoid filler. Use markdown formatting in responses.
"""

SAMPLE_ORION = """<!-- Orion directives -->

## Code Standards
Always use type hints. Keep functions under 30 lines.
Follow PEP 8 naming conventions.

## Debug Protocol
When debugging, show the full traceback and suggest three possible causes.
"""


# ------------------------------------------------------------------
def test_parser():
    print("\n=== Parser ===")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "shared.md")
        write_file(path, SAMPLE_SHARED)

        sections = parse_directive_file(path, "shared")
        check("parses 3 sections", len(sections) == 3)
        check("first heading", sections[0].heading == "First Words Protocol")
        check("second heading", sections[1].heading == "Project Context")
        check("third heading", sections[2].heading == "Communication Style")
        check("scope is shared", all(s.scope == "shared" for s in sections))
        check("source_file set", all(s.source_file == "shared.md" for s in sections))
        check("body not empty", all(s.body for s in sections))
        check("comments stripped", "<!--" not in sections[0].body)

        # Missing file returns empty
        empty = parse_directive_file(os.path.join(tmp, "nonexistent.md"), "test")
        check("missing file returns empty", empty == [])

        # Empty section is skipped
        sparse = "## Has Content\nSome text\n\n## Empty Section\n\n## Another\nMore text"
        write_file(os.path.join(tmp, "sparse.md"), sparse)
        sparse_sections = parse_directive_file(os.path.join(tmp, "sparse.md"), "test")
        check("empty section skipped", len(sparse_sections) == 2)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
def test_store_search():
    print("\n=== Store Search ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)

        store = DirectiveStore(tmp, scopes=["shared", "orion"])

        # Search for code-related content
        results = store.search("code standards type hints")
        check("search finds code standards", len(results) > 0)
        check("top result is code standards",
              results[0].heading == "Code Standards")

        # Search for greeting
        results2 = store.search("greeting the user")
        check("search finds first words", len(results2) > 0)
        check("top result is first words",
              results2[0].heading == "First Words Protocol")

        # No match
        results3 = store.search("xyzzy nonexistent gibberish")
        check("no-match returns empty", len(results3) == 0)

        # Limit
        results4 = store.search("agent runtime", limit=1)
        check("limit caps results", len(results4) <= 1)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
def test_store_list_and_get():
    print("\n=== Store List & Get ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)

        store = DirectiveStore(tmp, scopes=["shared", "orion"])

        headings = store.list_headings()
        check("lists all 5 headings", len(headings) == 5)
        heading_names = [h["heading"] for h in headings]
        check("contains Code Standards", "Code Standards" in heading_names)
        check("contains Project Context", "Project Context" in heading_names)

        # Get by exact heading
        section = store.get_section("Debug Protocol")
        check("get finds section", section is not None)
        check("get correct heading", section.heading == "Debug Protocol")
        check("get has body", "traceback" in section.body.lower())

        # Case-insensitive get
        section2 = store.get_section("debug protocol")
        check("get case-insensitive", section2 is not None)

        # Missing heading
        section3 = store.get_section("Nonexistent Section")
        check("get missing returns None", section3 is None)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
def test_store_scoping():
    print("\n=== Store Scoping ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)

        # Only shared scope
        store_shared = DirectiveStore(tmp, scopes=["shared"])
        check("shared-only sees 3", len(store_shared.get_all()) == 3)

        # Only orion scope
        store_orion = DirectiveStore(tmp, scopes=["orion"])
        check("orion-only sees 2", len(store_orion.get_all()) == 2)

        # Both scopes
        store_both = DirectiveStore(tmp, scopes=["shared", "orion"])
        check("combined sees 5", len(store_both.get_all()) == 5)

        # String scope
        store_str = DirectiveStore(tmp, scopes="shared")
        check("string scope works", len(store_str.get_all()) == 3)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
def test_injector():
    print("\n=== Injector ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        store = DirectiveStore(tmp, scopes=["shared"])

        # With query
        block = build_directives_block(store, query="project runtime python")
        check("block contains header", "## Active Directives" in block)
        check("block contains project context", "Project Context" in block)

        # Without query (returns all)
        block_all = build_directives_block(store)
        check("no-query returns all sections", "First Words" in block_all)
        check("block has scope tag", "*(scope: shared)*" in block_all)

        # Max sections
        block_limited = build_directives_block(store, max_sections=1)
        check("max_sections limits output", block_limited.count("###") == 1)

        # Empty store
        empty_store = DirectiveStore(tmp, scopes=["nonexistent"])
        block_empty = build_directives_block(empty_store, query="anything")
        check("empty store returns empty string", block_empty == "")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
def test_tool():
    print("\n=== Directives Tool ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)

        # Patch the tool's directory constant for testing
        import src.tools.directives_tool as dt_mod
        orig_dir = dt_mod._DIRECTIVES_DIR
        dt_mod._DIRECTIVES_DIR = tmp

        tool = DirectivesTool()

        # Definition exists
        defn = tool.definition()
        check("tool definition has name", defn["name"] == "directives")

        # List action (pass scope=orion to include shared + orion)
        result = json.loads(tool.execute({"action": "list", "scope": "orion"}))
        check("list returns ok", result["status"] == "ok")
        check("list count is 5", result["count"] == 5)

        # Search action
        result2 = json.loads(tool.execute({"action": "search", "query": "type hints PEP 8", "scope": "orion"}))
        check("search returns ok", result2["status"] == "ok")
        check("search finds results", result2["count"] > 0)
        check("search has sections", len(result2["sections"]) > 0)

        # Get action
        result3 = json.loads(tool.execute({"action": "get", "heading": "Debug Protocol", "scope": "orion"}))
        check("get returns ok", result3["status"] == "ok")
        check("get has body", "traceback" in result3["body"].lower())

        # Get missing
        result4 = json.loads(tool.execute({"action": "get", "heading": "Nonexistent"}))
        check("get missing returns not_found", result4["status"] == "not_found")

        # Search without query
        result5 = json.loads(tool.execute({"action": "search"}))
        check("search no query returns error", result5["status"] == "error")

        # Unknown action
        result6 = json.loads(tool.execute({"action": "write"}))
        check("unknown action returns error", result6["status"] == "error")

        # Restore original
        dt_mod._DIRECTIVES_DIR = orig_dir

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
def test_scoring():
    print("\n=== Scoring ===")
    section = DirectiveSection(
        heading="Python Code Standards",
        body="Always use type hints. Follow PEP 8 naming conventions.",
        scope="shared",
        source_file="test.md",
    )

    # Matching query
    s1 = score_section("python type hints", section)
    check("matching query scores > 0", s1 > 0)

    # No overlap
    s2 = score_section("xyzzy gibberish", section)
    check("no overlap scores 0", s2 == 0.0)

    # Empty query
    s3 = score_section("", section)
    check("empty query scores 0", s3 == 0.0)

    # Higher relevance = higher score
    s_relevant = score_section("python type hints", section)
    s_irrelevant = score_section("weather forecast", section)
    check("relevant query beats irrelevant", s_relevant > s_irrelevant)


def test_manifest_generation():
    print("\n=== Manifest Generation ===")
    tmp = tempfile.mkdtemp()
    try:
        # Write test directive files
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)
        write_file(os.path.join(tmp, "elysia.md"), "<!-- empty -->")

        manifest = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        check("manifest_version is 1", manifest["manifest_version"] == 1)
        check("hash_algo is sha256", manifest["hash_algo"] == "sha256")
        check("generated_utc present", "generated_utc" in manifest)
        check("root_paths present", manifest["root_paths"] == ["directives/"])
        check("default_retrieval_mode present", manifest["default_retrieval_mode"] == "keyword_hybrid")

        directives = manifest["directives"]
        check("parsed 5 sections", len(directives) == 5)

        # Check structure of first entry
        first = directives[0]
        check("has id", "id" in first and "." in first["id"])
        check("has name", "name" in first and len(first["name"]) > 0)
        check("has scope", first["scope"] in ("shared", "orion", "elysia"))
        check("has risk", first["risk"] in ("low", "medium", "high"))
        check("has version", first["version"] == "1.0.0")
        check("has sha256", len(first["sha256"]) == 64)
        check("has path", first["path"].startswith("directives/"))
        check("has summary", len(first["summary"]) > 0)
        check("has triggers", isinstance(first["triggers"], list))
        check("has dependencies", isinstance(first["dependencies"], list))
        check("has status", first["status"] == "active")
        check("has token_estimate", isinstance(first["token_estimate"], int) and first["token_estimate"] > 0)

        # Check scopes are correct
        scopes = {d["scope"] for d in directives}
        check("shared scope present", "shared" in scopes)
        check("orion scope present", "orion" in scopes)

        # No duplicate IDs
        ids = [d["id"] for d in directives]
        check("no duplicate IDs", len(ids) == len(set(ids)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_manifest_save_load():
    print("\n=== Manifest Save/Load ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)
        write_file(os.path.join(tmp, "elysia.md"), "<!-- empty -->")

        manifest = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        manifest_path = os.path.join(tmp, "manifest.json")
        save_manifest(manifest, path=manifest_path)

        check("manifest file exists", os.path.isfile(manifest_path))

        loaded = load_manifest(path=manifest_path)
        check("loaded is not None", loaded is not None)
        check("loaded matches generated", loaded["manifest_version"] == manifest["manifest_version"])
        check("same directive count", len(loaded["directives"]) == len(manifest["directives"]))
        check("same IDs", [d["id"] for d in loaded["directives"]] == [d["id"] for d in manifest["directives"]])

        # Load from non-existent path
        missing = load_manifest(path=os.path.join(tmp, "missing.json"))
        check("load missing returns None", missing is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_manifest_helpers():
    print("\n=== Manifest Helpers ===")
    check("heading_to_id basic", _heading_to_id("orion", "Humor & Play Mode") == "orion.humor_play_mode")
    check("heading_to_id spaces", _heading_to_id("shared", "Core Identity") == "shared.core_identity")
    check("heading_to_id special chars", _heading_to_id("elysia", "Elysia's Protocol (v1)") == "elysia.elysias_protocol_v1")
    check("sha256 deterministic", _sha256("hello") == _sha256("hello"))
    check("sha256 different inputs differ", _sha256("hello") != _sha256("world"))
    check("sha256 length", len(_sha256("test")) == 64)


def test_tool_manifest():
    print("\n=== Tool: Manifest Action ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)
        write_file(os.path.join(tmp, "elysia.md"), "<!-- empty -->")

        # Generate and save a manifest so the tool can load it
        manifest = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        manifest_path = os.path.join(tmp, "manifest.json")
        save_manifest(manifest, path=manifest_path)

        # Test via the generate_manifest function directly (tool uses load_manifest internally)
        result = manifest
        check("manifest has directives", len(result["directives"]) > 0)
        check("all have id", all("id" in d for d in result["directives"]))
        check("all have sha256", all("sha256" in d for d in result["directives"]))
        check("all have status", all("status" in d for d in result["directives"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_manifest_diff():
    print("\n=== Manifest Diff ===")
    tmp = tempfile.mkdtemp()
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)
        write_file(os.path.join(tmp, "elysia.md"), "<!-- empty -->")

        # Generate baseline and save
        baseline = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        manifest_path = os.path.join(tmp, "manifest.json")
        save_manifest(baseline, path=manifest_path)

        # No changes — diff should be clean
        live = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        diff = diff_manifest(baseline, live)
        check("no changes: added=0", diff["total_added"] == 0)
        check("no changes: removed=0", diff["total_removed"] == 0)
        check("no changes: changed=0", diff["total_changed"] == 0)
        check("no changes: unchanged=5", diff["unchanged_count"] == 5)

        # Add a new section to orion
        updated_orion = SAMPLE_ORION + "\n## New Orion Section\nBrand new content.\n"
        write_file(os.path.join(tmp, "orion.md"), updated_orion)
        live2 = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        diff2 = diff_manifest(baseline, live2)
        check("added section: added=1", diff2["total_added"] == 1)
        check("added section: name correct", diff2["added"][0]["scope"] == "orion")

        # Modify content of existing section
        modified_shared = SAMPLE_SHARED.replace("Be direct.", "Be extremely direct.")
        write_file(os.path.join(tmp, "shared.md"), modified_shared)
        # Reset orion to baseline so only shared changes are measured
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)
        live3 = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        diff3 = diff_manifest(baseline, live3)
        check("modified section: changed>0", diff3["total_changed"] > 0)
        check("changed entry has old_sha256", "old_sha256" in diff3["changed"][0])
        check("changed entry has new_sha256", "new_sha256" in diff3["changed"][0])
        check("hashes differ", diff3["changed"][0]["old_sha256"] != diff3["changed"][0]["new_sha256"])

        # Remove a section by rewriting shared with fewer sections
        minimal_shared = "## First Words Protocol\nWhen greeting the user.\n"
        write_file(os.path.join(tmp, "shared.md"), minimal_shared)
        live4 = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        diff4 = diff_manifest(baseline, live4)
        check("removed sections: removed>0", diff4["total_removed"] > 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_changes():
    print("\n=== Audit Changes ===")
    tmp = tempfile.mkdtemp()
    import src.directives.manifest as _mmod
    orig_scopes = _mmod.SCOPES
    _mmod.SCOPES = ("shared", "orion")
    try:
        write_file(os.path.join(tmp, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(tmp, "orion.md"), SAMPLE_ORION)
        write_file(os.path.join(tmp, "elysia.md"), "<!-- empty -->")

        # No persisted manifest — all directives should be "added"
        diff = audit_changes(directives_dir=tmp, manifest_path_override=os.path.join(tmp, "manifest.json"))
        check("fresh audit: all added", diff["total_added"] == 5)
        check("fresh audit: none removed", diff["total_removed"] == 0)

        # Save manifest, then audit again — should be clean
        manifest = generate_manifest(directives_dir=tmp, scopes=("shared", "orion"))
        save_manifest(manifest, path=os.path.join(tmp, "manifest.json"))
        diff2 = audit_changes(directives_dir=tmp, manifest_path_override=os.path.join(tmp, "manifest.json"))
        check("saved audit: no changes", diff2["total_added"] == 0 and diff2["total_changed"] == 0)
    finally:
        _mmod.SCOPES = orig_scopes
        shutil.rmtree(tmp, ignore_errors=True)


def test_tool_changes_action():
    print("\n=== Tool: Changes Action ===")
    # The changes action calls audit_changes() which uses default paths.
    # We test the response shape by calling execute directly.
    result = json.loads(DirectivesTool.execute({"action": "changes"}))
    check("changes has status", result["status"] == "ok")
    check("changes has total_added", "total_added" in result)
    check("changes has total_removed", "total_removed" in result)
    check("changes has total_changed", "total_changed" in result)
    check("changes has unchanged_count", "unchanged_count" in result)
    check("changes has added list", isinstance(result["added"], list))
    check("changes has changed list", isinstance(result["changed"], list))


# ------------------------------------------------------------------
if __name__ == "__main__":
    test_parser()
    test_store_search()
    test_store_list_and_get()
    test_store_scoping()
    test_injector()
    test_tool()
    test_scoring()
    test_manifest_generation()
    test_manifest_save_load()
    test_manifest_helpers()
    test_tool_manifest()
    test_manifest_diff()
    test_audit_changes()
    test_tool_changes_action()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL == 0:
        print("All tests passed.")
    else:
        sys.exit(1)
