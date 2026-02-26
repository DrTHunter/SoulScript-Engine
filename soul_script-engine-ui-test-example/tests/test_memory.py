"""Tests for the Memory Vault system.

Run from project root:
    python -m tests.test_memory
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory.vault import VaultStore, MemoryVault
from src.memory.types import Memory, VALID_SCOPES, VALID_TIERS, VALID_CATEGORIES, VALID_SOURCES
from src.memory.pii_guard import check_pii

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


def make_vault(tmp_dir=None):
    """Create a VaultStore pointed at a temp directory."""
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    path = os.path.join(tmp_dir, "vault.jsonl")
    return VaultStore(path), tmp_dir


# ------------------------------------------------------------------
def test_create_and_read():
    """Basic create_memory + read_active round-trip."""
    print("\n=== Create & Read ===")
    vault, tmp = make_vault()
    try:
        mem = vault.create_memory("Creator likes black coffee", "shared", "preference")
        check("create returns Memory", isinstance(mem, Memory))
        check("has 12-char id", len(mem.id) == 12)
        check("scope stored", mem.scope == "shared")
        check("category stored", mem.category == "preference")
        check("tier defaults to canon", mem.tier == "canon")
        check("version is 1", mem.version == 1)
        check("is active", mem.is_active())
        check("created_at populated", len(mem.created_at) > 0)

        active = vault.read_active()
        check("read_active returns 1", len(active) == 1)
        check("text matches", active[0].text == "Creator likes black coffee")

        # get_memory by id
        fetched = vault.get_memory(mem.id)
        check("get_memory finds it", fetched is not None)
        check("get_memory text matches", fetched.text == mem.text)

        # get_memory for non-existent id
        missing = vault.get_memory("nonexistent")
        check("get_memory missing returns None", missing is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_scoping():
    """Memories respect scope assignment."""
    print("\n=== Scoping ===")
    vault, tmp = make_vault()
    try:
        vault.create_memory("Shared fact", "shared", "bio")
        vault.create_memory("Astraea fact", "astraea", "identity")
        vault.create_memory("Callum fact", "callum", "identity")

        active = vault.read_active()
        check("3 memories total", len(active) == 3)

        scopes = {m.scope for m in active}
        check("shared scope present", "shared" in scopes)
        check("astraea scope present", "astraea" in scopes)
        check("callum scope present", "callum" in scopes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pii_guard():
    """PII detection blocks memory creation."""
    print("\n=== PII Guard ===")
    vault, tmp = make_vault()
    try:
        # SSN pattern
        blocked = False
        try:
            vault.create_memory("My SSN is 123-45-6789", "shared", "bio")
        except ValueError:
            blocked = True
        check("SSN blocked", blocked)

        # Credit card pattern
        blocked = False
        try:
            vault.create_memory("Card: 4111 1111 1111 1111", "shared", "bio")
        except ValueError:
            blocked = True
        check("credit card blocked", blocked)

        # Password keyword
        blocked = False
        try:
            vault.create_memory("password: hunter2", "shared", "bio")
        except ValueError:
            blocked = True
        check("password keyword blocked", blocked)

        # API key keyword
        blocked = False
        try:
            vault.create_memory("api_key: sk-abc123", "shared", "meta")
        except ValueError:
            blocked = True
        check("api_key keyword blocked", blocked)

        # Safe text passes
        mem = vault.create_memory("Creator is a software engineer", "shared", "bio")
        check("safe text passes", mem is not None)

        # check_pii standalone
        violations = check_pii("secret_key: xyz")
        check("check_pii detects secrets", len(violations) > 0)

        clean = check_pii("Normal conversation text")
        check("check_pii clean text", len(clean) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_update():
    """update_memory appends new version."""
    print("\n=== Update ===")
    vault, tmp = make_vault()
    try:
        mem = vault.create_memory("Original text", "shared", "preference")

        updated = vault.update_memory(mem.id, text="Updated text")
        check("update returns Memory", isinstance(updated, Memory))
        check("version incremented", updated.version == 2)
        check("text updated", updated.text == "Updated text")
        check("scope preserved", updated.scope == "shared")
        check("updated_at set", updated.updated_at is not None)

        # Read active should show updated version
        active = vault.read_active()
        check("still 1 active memory", len(active) == 1)
        check("active text is updated", active[0].text == "Updated text")

        # Raw lines should show 2 (original + update)
        raw = vault.read_all()
        check("2 raw lines", len(raw) == 2)

        # Update category
        updated2 = vault.update_memory(mem.id, category="goal")
        check("category changed", updated2.category == "goal")
        check("version 3", updated2.version == 3)

        # Update tags
        updated3 = vault.update_memory(mem.id, tags=["coffee", "beverage"])
        check("tags updated", updated3.tags == ["coffee", "beverage"])

        # Update tier
        updated4 = vault.update_memory(mem.id, tier="register")
        check("tier updated", updated4.tier == "register")

        # Update non-existent memory
        not_found = False
        try:
            vault.update_memory("nonexistent", text="hello")
        except KeyError:
            not_found = True
        check("update missing raises KeyError", not_found)

        # Update with PII blocked
        pii_blocked = False
        try:
            vault.update_memory(mem.id, text="password: secret123")
        except ValueError:
            pii_blocked = True
        check("update with PII blocked", pii_blocked)

        # Update with empty text blocked
        empty_blocked = False
        try:
            vault.update_memory(mem.id, text="   ")
        except ValueError:
            empty_blocked = True
        check("update with empty text blocked", empty_blocked)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_delete():
    """delete_memory soft-deletes with tombstone."""
    print("\n=== Delete ===")
    vault, tmp = make_vault()
    try:
        m1 = vault.create_memory("Memory one", "shared", "bio")
        m2 = vault.create_memory("Memory two", "shared", "preference")

        # Delete first memory
        result = vault.delete_memory(m1.id)
        check("delete returns True", result is True)

        active = vault.read_active()
        check("1 active after delete", len(active) == 1)
        check("surviving memory correct", active[0].text == "Memory two")

        # get_memory should not find deleted
        gone = vault.get_memory(m1.id)
        check("get_memory returns None for deleted", gone is None)

        # Delete non-existent
        result2 = vault.delete_memory("nonexistent")
        check("delete missing returns False", result2 is False)

        # Double-delete
        result3 = vault.delete_memory(m1.id)
        check("double-delete returns False", result3 is False)

        # Tombstone visible in resolve_latest
        resolved = vault.resolve_latest()
        check("deleted memory in resolved", m1.id in resolved)
        check("tombstone has deleted_at", resolved[m1.id].deleted_at is not None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_bulk_delete():
    """bulk_delete handles multiple IDs."""
    print("\n=== Bulk Delete ===")
    vault, tmp = make_vault()
    try:
        m1 = vault.create_memory("Memory A", "shared", "bio")
        m2 = vault.create_memory("Memory B", "shared", "preference")
        m3 = vault.create_memory("Memory C", "shared", "goal")

        result = vault.bulk_delete([m1.id, m3.id, "nonexistent"])
        check("deleted 2", len(result["deleted"]) == 2)
        check("not_found 1", len(result["not_found"]) == 1)

        active = vault.read_active()
        check("1 active remains", len(active) == 1)
        check("survivor is B", active[0].text == "Memory B")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_resolve_latest():
    """resolve_latest deduplicates multi-version records."""
    print("\n=== Resolve Latest ===")
    vault, tmp = make_vault()
    try:
        mem = vault.create_memory("v1", "shared", "bio")
        vault.update_memory(mem.id, text="v2")
        vault.update_memory(mem.id, text="v3")

        resolved = vault.resolve_latest()
        check("1 unique id", len(resolved) == 1)
        check("latest version is 3", resolved[mem.id].version == 3)
        check("latest text is v3", resolved[mem.id].text == "v3")

        # Raw should have 3 lines
        raw = vault.read_all()
        check("3 raw lines total", len(raw) == 3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_compact():
    """compact() rewrites vault to active-only."""
    print("\n=== Compact ===")
    vault, tmp = make_vault()
    try:
        m1 = vault.create_memory("Keep this", "shared", "bio")
        m2 = vault.create_memory("Delete this", "shared", "meta")
        vault.update_memory(m1.id, text="Keep this updated")
        vault.delete_memory(m2.id)

        # Before compact: 4 lines (create, create, update, tombstone)
        check("4 raw lines before", len(vault.read_all()) == 4)

        result = vault.compact()
        check("compact returns dict", isinstance(result, dict))
        check("lines_before is 4", result["lines_before"] == 4)
        check("lines_after is 1", result["lines_after"] == 1)
        check("lines_removed is 3", result["lines_removed"] == 3)

        # After compact
        active = vault.read_active()
        check("1 active after compact", len(active) == 1)
        check("text is updated", active[0].text == "Keep this updated")

        raw = vault.read_all()
        check("1 raw line after compact", len(raw) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_stats():
    """stats() returns correct counts and breakdowns."""
    print("\n=== Stats ===")
    vault, tmp = make_vault()
    try:
        vault.create_memory("Bio fact", "shared", "bio")
        vault.create_memory("Identity", "astraea", "identity")
        vault.create_memory("Goal 1", "shared", "goal", tier="register")
        m4 = vault.create_memory("Deleted", "callum", "meta")
        vault.delete_memory(m4.id)

        s = vault.stats()
        check("active_count is 3", s["active_count"] == 3)
        check("deleted_count is 1", s["deleted_count"] == 1)
        check("raw_lines is 5", s["raw_lines"] == 5)
        check("by_scope has shared", s["by_scope"].get("shared", 0) == 2)
        check("by_scope has astraea", s["by_scope"].get("astraea", 0) == 1)
        check("by_category has bio", s["by_category"].get("bio", 0) == 1)
        check("by_category has goal", s["by_category"].get("goal", 0) == 1)
        check("by_tier has canon", s["by_tier"].get("canon", 0) == 2)
        check("by_tier has register", s["by_tier"].get("register", 0) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_empty_vault():
    """Operations on empty vault behave correctly."""
    print("\n=== Empty Vault ===")
    vault, tmp = make_vault()
    try:
        check("read_all empty", vault.read_all() == [])
        check("read_active empty", vault.read_active() == [])
        check("resolve_latest empty", vault.resolve_latest() == {})
        check("get_memory returns None", vault.get_memory("any") is None)
        check("delete returns False", vault.delete_memory("any") is False)

        s = vault.stats()
        check("stats active_count 0", s["active_count"] == 0)
        check("stats deleted_count 0", s["deleted_count"] == 0)
        check("stats raw_lines 0", s["raw_lines"] == 0)

        result = vault.bulk_delete(["a", "b"])
        check("bulk_delete all not_found", len(result["not_found"]) == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_memory_dataclass():
    """Memory dataclass round-trips through to_dict/from_dict."""
    print("\n=== Memory Dataclass ===")
    mem = Memory(
        id="abc123",
        text="Test memory",
        scope="shared",
        category="bio",
        tier="canon",
        topic_id="topic-1",
        tags=["test", "unit"],
        created_at="2025-01-01T00:00:00",
        source="manual",
        version=1,
    )
    d = mem.to_dict()
    check("to_dict has id", d["id"] == "abc123")
    check("to_dict has text", d["text"] == "Test memory")
    check("to_dict has scope", d["scope"] == "shared")
    check("to_dict has category", d["category"] == "bio")
    check("to_dict has tier", d["tier"] == "canon")
    check("to_dict has topic_id", d["topic_id"] == "topic-1")
    check("to_dict has tags", d["tags"] == ["test", "unit"])
    check("to_dict has version", d["version"] == 1)

    restored = Memory.from_dict(d)
    check("from_dict round-trip id", restored.id == mem.id)
    check("from_dict round-trip text", restored.text == mem.text)
    check("from_dict round-trip scope", restored.scope == mem.scope)
    check("from_dict round-trip tier", restored.tier == mem.tier)
    check("from_dict round-trip topic_id", restored.topic_id == mem.topic_id)
    check("from_dict round-trip tags", restored.tags == mem.tags)

    # Backward compat: missing tier defaults to canon
    d_old = {"id": "old1", "text": "old", "scope": "shared", "category": "bio"}
    old = Memory.from_dict(d_old)
    check("missing tier defaults canon", old.tier == "canon")
    check("missing version defaults 1", old.version == 1)

    # is_active
    check("active when no deleted_at", mem.is_active())
    deleted = Memory(id="d1", text="x", scope="shared", category="bio", deleted_at="2025-01-01")
    check("deleted when deleted_at set", not deleted.is_active())


def test_validation_constants():
    """Taxonomy constants are populated."""
    print("\n=== Validation Constants ===")
    check("VALID_SCOPES has shared", "shared" in VALID_SCOPES)
    check("VALID_SCOPES is frozenset", isinstance(VALID_SCOPES, frozenset))
    check("VALID_TIERS has canon", "canon" in VALID_TIERS)
    check("VALID_TIERS has register", "register" in VALID_TIERS)
    check("VALID_TIERS excludes log", "log" not in VALID_TIERS)
    check("VALID_CATEGORIES has bio", "bio" in VALID_CATEGORIES)
    check("VALID_CATEGORIES has preference", "preference" in VALID_CATEGORIES)
    check("VALID_SOURCES has chat", "chat" in VALID_SOURCES)
    check("VALID_SOURCES has manual", "manual" in VALID_SOURCES)


def test_tiers_and_topics():
    """Tier and topic_id are stored correctly."""
    print("\n=== Tiers & Topics ===")
    vault, tmp = make_vault()
    try:
        # Canon tier (default)
        m1 = vault.create_memory("Canon fact", "shared", "bio")
        check("default tier is canon", m1.tier == "canon")

        # Register tier with topic_id
        m2 = vault.create_memory(
            "Current project: SoulScript",
            "shared", "project",
            tier="register", topic_id="project-soulscript",
        )
        check("register tier stored", m2.tier == "register")
        check("topic_id stored", m2.topic_id == "project-soulscript")

        # Update by topic — first find by topic, then update
        active = vault.read_active()
        topic_mem = [m for m in active if m.topic_id == "project-soulscript"]
        check("find by topic_id", len(topic_mem) == 1)

        updated = vault.update_memory(topic_mem[0].id, text="SoulScript v2")
        check("topic update preserves topic_id", updated.topic_id == "project-soulscript")
        check("topic update changes text", updated.text == "SoulScript v2")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_tags_and_source():
    """Tags and source fields round-trip correctly."""
    print("\n=== Tags & Source ===")
    vault, tmp = make_vault()
    try:
        mem = vault.create_memory(
            "Tagged memory",
            "shared", "preference",
            tags=["coffee", "morning"],
            source="chat",
        )
        check("tags stored", mem.tags == ["coffee", "morning"])
        check("source stored", mem.source == "chat")

        # Read back
        fetched = vault.get_memory(mem.id)
        check("tags round-trip", fetched.tags == ["coffee", "morning"])
        check("source round-trip", fetched.source == "chat")

        # Default source
        m2 = vault.create_memory("No source", "shared", "meta")
        check("default source is manual", m2.source == "manual")

        # Default tags
        check("default tags is empty list", m2.tags == [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_create_validation():
    """create_memory validates inputs."""
    print("\n=== Create Validation ===")
    vault, tmp = make_vault()
    try:
        # Empty text
        empty_err = False
        try:
            vault.create_memory("", "shared", "bio")
        except ValueError:
            empty_err = True
        check("empty text raises ValueError", empty_err)

        # Whitespace-only text
        ws_err = False
        try:
            vault.create_memory("   ", "shared", "bio")
        except ValueError:
            ws_err = True
        check("whitespace text raises ValueError", ws_err)

        # Scope lowercased
        mem = vault.create_memory("Test", "SHARED", "bio")
        check("scope lowercased", mem.scope == "shared")

        # Category lowercased
        mem2 = vault.create_memory("Test2", "shared", "BIO")
        check("category lowercased", mem2.category == "bio")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_jsonl_format():
    """Vault file is valid JSONL."""
    print("\n=== JSONL Format ===")
    vault, tmp = make_vault()
    try:
        vault.create_memory("Line one", "shared", "bio")
        vault.create_memory("Line two", "shared", "preference")

        with open(vault.path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        check("2 lines in file", len(lines) == 2)

        # Each line is valid JSON
        parsed = []
        for ln in lines:
            parsed.append(json.loads(ln))
        check("all lines parse as JSON", len(parsed) == 2)
        check("first has id", "id" in parsed[0])
        check("first has text", "text" in parsed[0])
        check("first has scope", "scope" in parsed[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_backward_compat_alias():
    """MemoryVault is an alias for VaultStore."""
    print("\n=== Backward Compat ===")
    check("MemoryVault is VaultStore", MemoryVault is VaultStore)

    # Can instantiate via alias
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "vault.jsonl")
        vault = MemoryVault(path)
        mem = vault.create_memory("Via alias", "shared", "bio")
        check("alias create works", isinstance(mem, Memory))
        check("alias read works", len(vault.read_active()) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
if __name__ == "__main__":
    test_create_and_read()
    test_scoping()
    test_pii_guard()
    test_update()
    test_delete()
    test_bulk_delete()
    test_resolve_latest()
    test_compact()
    test_stats()
    test_empty_vault()
    test_memory_dataclass()
    test_validation_constants()
    test_tiers_and_topics()
    test_tags_and_source()
    test_create_validation()
    test_jsonl_format()
    test_backward_compat_alias()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL == 0:
        print("All tests passed.")
    else:
        sys.exit(1)
