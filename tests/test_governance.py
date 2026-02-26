"""Tests for governance modules: ActiveDirectives, validate_manifest.

Run from project root:
    python -m tests.test_governance
"""

import json
import os
import sys
import tempfile
import shutil
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.governance.active_directives import ActiveDirectives, _ActiveEntry
from src.directives.manifest import (
    validate_manifest,
    generate_manifest,
    _sha256,
    _heading_to_id,
    _estimate_tokens,
    _REQUIRED_TOP_KEYS,
    _REQUIRED_ENTRY_KEYS,
    _VALID_SCOPES,
    _VALID_STATUSES,
    _VALID_RISKS,
)

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


# ------------------------------------------------------------------
# Helpers for building mock directive sections
# ------------------------------------------------------------------

class FakeSection:
    """Minimal stand-in for DirectiveSection."""
    def __init__(self, heading, body, scope, source_file="test.md"):
        self.heading = heading
        self.body = body
        self.scope = scope
        self.source_file = source_file


SAMPLE_SHARED = """\
## First Words Protocol
When greeting the user, reference recent context.

## Project Context
The user is building a multi-agent runtime.
"""

SAMPLE_ORION = """\
## Code Standards
Always use type hints. Follow PEP 8.

## Debug Protocol
Show the full traceback and suggest three possible causes.
"""


def _build_valid_manifest(directives_dir):
    """Generate a real manifest from the sample files."""
    return generate_manifest(directives_dir=directives_dir)


def _build_minimal_manifest():
    """Return a minimal valid-ish manifest dict (no live file checks)."""
    return {
        "manifest_version": "1.0",
        "generated_utc": "2025-01-01T00:00:00Z",
        "hash_algo": "sha256",
        "root_paths": ["directives/"],
        "default_retrieval_mode": "relevance",
        "directives": [
            {
                "id": "shared.first-words-protocol",
                "name": "First Words Protocol",
                "scope": "shared",
                "risk": "low",
                "version": "1",
                "sha256": "abc123",
                "path": "directives/shared.md",
                "summary": "Greet warmly",
                "triggers": ["session_start"],
                "dependencies": [],
                "status": "active",
                "token_estimate": 42,
            }
        ],
    }


# ==================================================================
# ActiveDirectives tests
# ==================================================================

def test_active_directives_reset():
    print("\n=== ActiveDirectives: reset ===")
    ActiveDirectives.reset()
    check("empty after reset", ActiveDirectives.count() == 0)
    check("list is empty", ActiveDirectives.list() == [])
    check("ids is empty", ActiveDirectives.ids() == [])
    check("summary count=0", ActiveDirectives.summary()["count"] == 0)


def test_active_directives_record():
    print("\n=== ActiveDirectives: record ===")
    ActiveDirectives.reset()
    entry = ActiveDirectives.record("Test Heading", "Body text", "shared")
    check("returns dict", isinstance(entry, dict))
    check("has id", "id" in entry)
    check("has name", entry["name"] == "Test Heading")
    check("has scope", entry["scope"] == "shared")
    check("has sha256", len(entry["sha256"]) == 64)
    check("has loaded_at_utc", "loaded_at_utc" in entry)
    check("has token_estimate", entry["token_estimate"] > 0)
    check("version is unknown (no manifest)", entry["version"] == "unknown")
    check("count is 1", ActiveDirectives.count() == 1)

    # Record with manifest_entry
    ActiveDirectives.reset()
    me = {"id": "custom.id", "version": "3"}
    entry2 = ActiveDirectives.record("Another", "Body", "orion", manifest_entry=me)
    check("uses manifest id", entry2["id"] == "custom.id")
    check("uses manifest version", entry2["version"] == "3")


def test_active_directives_record_sections():
    print("\n=== ActiveDirectives: record_sections ===")
    ActiveDirectives.reset()
    sections = [
        FakeSection("First Words Protocol", "Greet warmly.", "shared"),
        FakeSection("Code Standards", "Use type hints.", "orion"),
    ]
    results = ActiveDirectives.record_sections(sections)
    check("2 results", len(results) == 2)
    check("count is 2", ActiveDirectives.count() == 2)
    check("first name", results[0]["name"] == "First Words Protocol")
    check("second scope", results[1]["scope"] == "orion")

    # With manifest cross-reference
    ActiveDirectives.reset()
    manifest = {
        "directives": [
            {"name": "First Words Protocol", "id": "shared.first-words", "version": "2"},
            {"name": "Code Standards", "id": "orion.code-standards", "version": "5"},
        ]
    }
    results2 = ActiveDirectives.record_sections(sections, manifest=manifest)
    check("manifest id used", results2[0]["id"] == "shared.first-words")
    check("manifest version used", results2[0]["version"] == "2")
    check("second manifest id", results2[1]["id"] == "orion.code-standards")
    check("second manifest version", results2[1]["version"] == "5")


def test_active_directives_list():
    print("\n=== ActiveDirectives: list ===")
    ActiveDirectives.reset()
    ActiveDirectives.record("A", "body a", "shared")
    ActiveDirectives.record("B", "body b", "orion")
    entries = ActiveDirectives.list()
    check("list len=2", len(entries) == 2)
    check("all dicts", all(isinstance(e, dict) for e in entries))
    check("first is A", entries[0]["name"] == "A")
    check("second is B", entries[1]["name"] == "B")


def test_active_directives_ids():
    print("\n=== ActiveDirectives: ids ===")
    ActiveDirectives.reset()
    ActiveDirectives.record("Heading X", "body x", "shared")
    ids = ActiveDirectives.ids()
    check("1 id", len(ids) == 1)
    check("id is string", isinstance(ids[0], str))
    check("id contains scope", "shared" in ids[0])


def test_active_directives_summary():
    print("\n=== ActiveDirectives: summary ===")
    ActiveDirectives.reset()
    ActiveDirectives.record("H1", "Short body", "shared")
    ActiveDirectives.record("H2", "Another body", "orion")
    s = ActiveDirectives.summary()
    check("count=2", s["count"] == 2)
    check("ids len=2", len(s["ids"]) == 2)
    check("scopes sorted", s["scopes"] == ["orion", "shared"])
    check("total_tokens > 0", s["total_tokens"] > 0)
    check("total_tokens is int", isinstance(s["total_tokens"], int))


def test_active_entry_slots():
    print("\n=== _ActiveEntry: __slots__ ===")
    e = _ActiveEntry(
        id="test.id", name="Test", scope="shared", version="1",
        sha256="a" * 64, loaded_at_utc="2025-01-01T00:00:00Z",
        token_estimate=42,
    )
    check("has id", e.id == "test.id")
    check("has scope", e.scope == "shared")
    check("to_dict works", isinstance(e.to_dict(), dict))
    check("to_dict has 7 keys", len(e.to_dict()) == 7)
    # __slots__ prevents arbitrary attribute assignment
    try:
        e.arbitrary = "nope"
        check("__slots__ enforced", False)
    except AttributeError:
        check("__slots__ enforced", True)


# ==================================================================
# ==================================================================
# validate_manifest tests
# ==================================================================

def test_validate_manifest_valid():
    print("\n=== validate_manifest: valid manifest ===")
    tmp = tempfile.mkdtemp()
    try:
        ddir = os.path.join(tmp, "directives")
        os.makedirs(ddir)
        write_file(os.path.join(ddir, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(ddir, "orion.md"), SAMPLE_ORION)

        manifest = _build_valid_manifest(ddir)
        result = validate_manifest(manifest, directives_dir=ddir)
        check("valid=True", result["valid"] is True)
        check("no errors", len(result["errors"]) == 0)
    finally:
        shutil.rmtree(tmp)


def test_validate_manifest_missing_top_keys():
    print("\n=== validate_manifest: missing top-level keys ===")
    result = validate_manifest({})
    check("not valid", result["valid"] is False)
    check("errors for missing keys", len(result["errors"]) >= len(_REQUIRED_TOP_KEYS))


def test_validate_manifest_missing_entry_keys():
    print("\n=== validate_manifest: missing entry keys ===")
    manifest = _build_minimal_manifest()
    # Remove some keys from the first directive
    del manifest["directives"][0]["risk"]
    del manifest["directives"][0]["summary"]
    result = validate_manifest(manifest, check_hashes=False)
    check("not valid", result["valid"] is False)
    error_text = " ".join(result["errors"])
    check("risk mentioned", "risk" in error_text)
    check("summary mentioned", "summary" in error_text)


def test_validate_manifest_invalid_enums():
    print("\n=== validate_manifest: invalid enum values ===")
    manifest = _build_minimal_manifest()
    manifest["directives"][0]["scope"] = "invalid_scope"
    manifest["directives"][0]["status"] = "bogus"
    manifest["directives"][0]["risk"] = "extreme"
    result = validate_manifest(manifest, check_hashes=False)
    check("not valid", result["valid"] is False)
    error_text = " ".join(result["errors"])
    check("invalid scope flagged", "invalid_scope" in error_text)
    check("bogus status flagged", "bogus" in error_text)
    check("extreme risk flagged", "extreme" in error_text)


def test_validate_manifest_duplicate_ids():
    print("\n=== validate_manifest: duplicate IDs ===")
    manifest = _build_minimal_manifest()
    dup = dict(manifest["directives"][0])
    manifest["directives"].append(dup)
    result = validate_manifest(manifest, check_hashes=False)
    check("not valid", result["valid"] is False)
    error_text = " ".join(result["errors"])
    check("duplicate flagged", "duplicate" in error_text.lower())


def test_validate_manifest_missing_source():
    print("\n=== validate_manifest: missing source file ===")
    tmp = tempfile.mkdtemp()
    try:
        ddir = os.path.join(tmp, "directives")
        os.makedirs(ddir)
        manifest = _build_minimal_manifest()
        # path points to a file that doesn't exist in ddir's parent
        manifest["directives"][0]["path"] = "directives/nonexistent.md"
        result = validate_manifest(manifest, directives_dir=ddir, check_hashes=False)
        check("not valid", result["valid"] is False)
        error_text = " ".join(result["errors"])
        check("source not found", "source not found" in error_text)
    finally:
        shutil.rmtree(tmp)


def test_validate_manifest_sha256_drift():
    print("\n=== validate_manifest: SHA-256 drift ===")
    tmp = tempfile.mkdtemp()
    try:
        ddir = os.path.join(tmp, "directives")
        os.makedirs(ddir)
        write_file(os.path.join(ddir, "shared.md"), SAMPLE_SHARED)
        write_file(os.path.join(ddir, "orion.md"), SAMPLE_ORION)

        manifest = _build_valid_manifest(ddir)
        check("valid before tamper", validate_manifest(manifest, directives_dir=ddir)["valid"])

        # Tamper with a hash
        manifest["directives"][0]["sha256"] = "0" * 64
        result = validate_manifest(manifest, directives_dir=ddir, check_hashes=True)
        check("not valid after tamper", result["valid"] is False)
        error_text = " ".join(result["errors"])
        check("sha256 drift flagged", "sha256 drift" in error_text)
    finally:
        shutil.rmtree(tmp)


def test_validate_manifest_enum_constants():
    print("\n=== validate_manifest: enum constants ===")
    check("shared in scopes", "shared" in _VALID_SCOPES)
    check("astraea in scopes", "astraea" in _VALID_SCOPES)
    check("callum in scopes", "callum" in _VALID_SCOPES)
    check("codex_animus in scopes", "codex_animus" in _VALID_SCOPES)
    check("active in statuses", "active" in _VALID_STATUSES)
    check("deprecated in statuses", "deprecated" in _VALID_STATUSES)
    check("experimental in statuses", "experimental" in _VALID_STATUSES)
    check("low in risks", "low" in _VALID_RISKS)
    check("medium in risks", "medium" in _VALID_RISKS)
    check("high in risks", "high" in _VALID_RISKS)


# ==================================================================
# Integration: injector populates ActiveDirectives
# ==================================================================

def test_injector_populates_active_directives():
    print("\n=== Injector: populates ActiveDirectives ===")
    from src.directives.store import DirectiveStore
    from src.directives.injector import build_directives_block

    ActiveDirectives.reset()
    tmp = tempfile.mkdtemp()
    try:
        ddir = os.path.join(tmp, "directives")
        os.makedirs(ddir)
        write_file(os.path.join(ddir, "shared.md"), SAMPLE_SHARED)

        store = DirectiveStore(ddir, scopes=["shared"])
        block = build_directives_block(store, max_sections=5)
        check("block non-empty", len(block) > 0)
        check("active count > 0", ActiveDirectives.count() > 0)

        # Verify section names match
        entries = ActiveDirectives.list()
        names = [e["name"] for e in entries]
        check("First Words Protocol tracked", "First Words Protocol" in names)
        check("Project Context tracked", "Project Context" in names)
    finally:
        ActiveDirectives.reset()
        shutil.rmtree(tmp)


# ==================================================================
# Main
# ==================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Governance Test Suite")
    print("=" * 60)

    # ActiveDirectives tests
    test_active_directives_reset()
    test_active_directives_record()
    test_active_directives_record_sections()
    test_active_directives_list()
    test_active_directives_ids()
    test_active_directives_summary()
    test_active_entry_slots()

    # validate_manifest tests
    test_validate_manifest_valid()
    test_validate_manifest_missing_top_keys()
    test_validate_manifest_missing_entry_keys()
    test_validate_manifest_invalid_enums()
    test_validate_manifest_duplicate_ids()
    test_validate_manifest_missing_source()
    test_validate_manifest_sha256_drift()
    test_validate_manifest_enum_constants()

    # Integration tests
    test_injector_populates_active_directives()

    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)
    if FAIL > 0:
        sys.exit(1)
