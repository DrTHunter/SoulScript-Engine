"""Tests for the Memory Vault system.

Run from project root:
    python -m tests.test_memory
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory.vault import MemoryVault
from src.memory.injector import build_memory_block
from src.memory.pii_guard import check_pii
from src.memory.types import Memory

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
# Helpers
# ------------------------------------------------------------------
def make_vault(tmp_dir, threshold=0.70, max_active=100, token_overlap=0.60):
    path = os.path.join(tmp_dir, "memory_vault.jsonl")
    return MemoryVault(
        path,
        similarity_threshold=threshold,
        max_active=max_active,
        token_overlap_threshold=token_overlap,
    )


# ------------------------------------------------------------------
# 1. Basic add + recall
# ------------------------------------------------------------------
def test_add_recall():
    print("\n=== Add & Recall ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        id1 = v.add_memory("User prefers dark mode", "shared", "preference", ["ui"])
        id2 = v.add_memory("Working on agent-runtime project", "orion", "project", ["python"])
        id3 = v.add_memory("Enjoys creative writing", "elysia", "preference", ["hobby"])

        check("add returns id", len(id1) == 12 and len(id2) == 12)

        all_mem = v.recall_memories()
        check("recall all returns 3", len(all_mem) == 3)

        shared = v.recall_memories(scope="shared")
        check("recall scope=shared returns 1", len(shared) == 1 and shared[0].scope == "shared")

        multi = v.recall_memories(scope=["shared", "orion"])
        check("recall scope=[shared,orion] returns 2", len(multi) == 2)

        prefs = v.recall_memories(category="preference")
        check("recall category=preference returns 2", len(prefs) == 2)

        tagged = v.recall_memories(tags=["ui"])
        check("recall tags=[ui] returns 1", len(tagged) == 1)

        limited = v.recall_memories(limit=1)
        check("recall limit=1 returns 1", len(limited) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 2. Scoping rules
# ------------------------------------------------------------------
def test_scoping():
    print("\n=== Scoping Rules ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        v.add_memory("Shared fact", "shared", "bio")
        v.add_memory("Orion-only fact", "orion", "bio")
        v.add_memory("Elysia-only fact", "elysia", "bio")

        orion_view = v.recall_memories(scope=["shared", "orion"])
        check("orion sees shared + orion", len(orion_view) == 2)
        check("orion does NOT see elysia",
              all(m.scope != "elysia" for m in orion_view))

        elysia_view = v.recall_memories(scope=["shared", "elysia"])
        check("elysia sees shared + elysia", len(elysia_view) == 2)
        check("elysia does NOT see orion",
              all(m.scope != "orion" for m in elysia_view))

        shared_only = v.recall_memories(scope="shared")
        check("shared-only returns 1", len(shared_only) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 3. Duplicate detection
# ------------------------------------------------------------------
def test_duplicates():
    print("\n=== Duplicate Detection ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp, threshold=0.85)
        v.add_memory("User prefers dark mode in all apps", "shared", "preference")

        # Near-duplicate (minor rewording)
        try:
            v.add_memory("User prefers dark mode in all applications", "shared", "preference")
            check("near-duplicate blocked", False, "should have raised")
        except ValueError as e:
            check("near-duplicate blocked", "Duplicate" in str(e))

        # Same text but different scope -> allowed
        id2 = v.add_memory("User prefers dark mode in all apps", "orion", "preference")
        check("same text different scope allowed", id2 is not None)

        # Clearly different text -> allowed
        id3 = v.add_memory("Favorite color is blue", "shared", "preference")
        check("different text allowed", id3 is not None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 4. PII guard
# ------------------------------------------------------------------
def test_pii():
    print("\n=== PII Guard ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)

        # SSN
        try:
            v.add_memory("My SSN is 123-45-6789", "shared", "bio")
            check("SSN blocked", False)
        except ValueError as e:
            check("SSN blocked", "PII" in str(e))

        # Password
        try:
            v.add_memory("password: hunter2", "shared", "bio")
            check("password blocked", False)
        except ValueError as e:
            check("password blocked", "PII" in str(e))

        # API key
        try:
            v.add_memory("api_key: sk-abc123", "shared", "bio")
            check("api_key blocked", False)
        except ValueError as e:
            check("api_key blocked", "PII" in str(e))

        # Safe text passes
        mid = v.add_memory("Favorite editor is VS Code", "shared", "preference")
        check("safe text allowed", mid is not None)

        # Direct check_pii function
        check("check_pii clean", check_pii("likes pizza") == [])
        check("check_pii ssn", len(check_pii("my ssn is 123-45-6789")) > 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 5. Search
# ------------------------------------------------------------------
def test_search():
    print("\n=== Search ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        v.add_memory("User prefers dark mode", "shared", "preference", ["ui"])
        v.add_memory("Working on Python agent runtime", "orion", "project", ["python", "ai"])
        v.add_memory("Enjoys writing science fiction stories", "elysia", "preference", ["writing"])
        v.add_memory("Uses Windows 11 as primary OS", "shared", "bio", ["os"])

        results = v.search_memories("python agent")
        check("search 'python agent' finds project",
              len(results) > 0 and "agent" in results[0].text.lower())

        results2 = v.search_memories("dark mode")
        check("search 'dark mode' finds preference",
              len(results2) > 0 and "dark mode" in results2[0].text.lower())

        results3 = v.search_memories("science fiction", scope="elysia")
        check("scoped search works",
              len(results3) == 1 and results3[0].scope == "elysia")

        results4 = v.search_memories("science fiction", scope="orion")
        check("scoped search excludes other scopes", len(results4) == 0)

        results5 = v.search_memories("xyzzy nonexistent query")
        check("no-match search returns empty", len(results5) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 6. Update
# ------------------------------------------------------------------
def test_update():
    print("\n=== Update ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        mid = v.add_memory("Favorite color is blue", "shared", "preference", ["color"])

        updated = v.update_memory(mid, text="Favorite color is green")
        check("text updated", updated.text == "Favorite color is green")
        check("updated_at set", updated.updated_at is not None)
        check("id preserved", updated.id == mid)
        check("tags preserved", updated.tags == ["color"])
        check("version incremented", updated.version == 2)

        updated2 = v.update_memory(mid, category="bio", tags=["color", "personal"])
        check("category updated", updated2.category == "bio")
        check("tags updated", updated2.tags == ["color", "personal"])
        check("version incremented again", updated2.version == 3)

        # Update non-existent
        try:
            v.update_memory("nonexistent", text="test")
            check("update missing raises", False)
        except KeyError:
            check("update missing raises", True)

        # PII in update blocked
        try:
            v.update_memory(mid, text="password: secret123")
            check("update PII blocked", False)
        except ValueError as e:
            check("update PII blocked", "PII" in str(e))

        # Verify original text preserved after blocked update
        current = v.recall_memories(scope="shared")
        check("text unchanged after blocked update",
              any(m.text == "Favorite color is green" for m in current))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 7. Soft delete
# ------------------------------------------------------------------
def test_delete():
    print("\n=== Soft Delete ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        id1 = v.add_memory("To be deleted", "shared", "meta")
        id2 = v.add_memory("To stay", "shared", "meta")

        check("2 active before delete", len(v.recall_memories()) == 2)

        result = v.delete_memory(id1)
        check("delete returns True", result is True)

        check("1 active after delete", len(v.recall_memories()) == 1)
        check("correct one remains", v.recall_memories()[0].id == id2)

        # The record is still in the file (soft delete)
        all_records = v._read_all()
        check("soft delete: record still in file", len(all_records) == 3)
        deleted = [m for m in all_records if m.id == id1][-1]
        check("deleted_at is set", deleted.deleted_at is not None)

        # Delete non-existent
        check("delete missing returns False", v.delete_memory("fake") is False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_bulk_delete():
    print("\n=== Bulk Delete ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        id1 = v.add_memory("The cat sat on a mat", "shared", "meta")
        id2 = v.add_memory("Docker containers use namespaces", "shared", "meta")
        id3 = v.add_memory("Parallel lines never intersect", "orion", "goal")
        id4 = v.add_memory("Rainfall patterns differ regionally", "elysia", "preference")

        check("4 active before bulk_delete", len(v.recall_memories()) == 4)

        # Bulk delete 2 valid + 1 invalid
        result = v.bulk_delete([id1, id3, "fake_id"])
        check("deleted_count == 2", len(result["deleted"]) == 2)
        check("id1 in deleted", id1 in result["deleted"])
        check("id3 in deleted", id3 in result["deleted"])
        check("fake_id in not_found", "fake_id" in result["not_found"])
        check("2 active after bulk_delete", len(v.recall_memories()) == 2)

        remaining_ids = {m.id for m in v.recall_memories()}
        check("id2 still active", id2 in remaining_ids)
        check("id4 still active", id4 in remaining_ids)

        # Bulk delete already-deleted id
        result2 = v.bulk_delete([id1])
        check("re-delete returns not_found", id1 in result2["not_found"])
        check("re-delete deleted_count == 0", len(result2["deleted"]) == 0)

        # Bulk delete empty list
        result3 = v.bulk_delete([])
        check("empty list returns empty results",
              len(result3["deleted"]) == 0 and len(result3["not_found"]) == 0)

        # Bulk delete all remaining
        result4 = v.bulk_delete([id2, id4])
        check("delete remaining count == 2", len(result4["deleted"]) == 2)
        check("0 active after full delete", len(v.recall_memories()) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_bulk_add():
    print("\n=== Bulk Add ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)

        # Bulk add multiple valid memories
        items = [
            {"text": "Bulk memory one", "scope": "shared", "category": "meta"},
            {"text": "Bulk memory two", "scope": "orion", "category": "goal", "tags": ["test"]},
            {"text": "Bulk memory three", "scope": "elysia", "category": "preference"},
        ]
        result = v.bulk_add(items)
        check("stored_count == 3", len(result["stored"]) == 3)
        check("no errors", len(result["errors"]) == 0)
        check("3 active", len(v.recall_memories()) == 3)

        # Verify indices are correct
        indices = [s["index"] for s in result["stored"]]
        check("indices are 0,1,2", indices == [0, 1, 2])

        # Bulk add with some failures (empty text, invalid scope, PII)
        mixed_items = [
            {"text": "Good memory", "scope": "shared", "category": "meta"},
            {"text": "", "scope": "shared", "category": "meta"},  # empty text
            {"text": "Bad scope", "scope": "invalid", "category": "meta"},  # invalid scope
            {"text": "SSN is 123-45-6789", "scope": "shared", "category": "meta"},  # PII
            {"text": "Another good one", "scope": "orion", "category": "goal"},
        ]
        result2 = v.bulk_add(mixed_items)
        check("mixed: stored_count == 2", len(result2["stored"]) == 2)
        check("mixed: error_count == 3", len(result2["errors"]) == 3)
        check("mixed: stored indices are 0,4",
              [s["index"] for s in result2["stored"]] == [0, 4])
        check("mixed: error indices are 1,2,3",
              [e["index"] for e in result2["errors"]] == [1, 2, 3])

        # Bulk add with duplicate detection
        dup_items = [
            {"text": "Bulk memory one", "scope": "shared", "category": "meta"},  # dup of first add
        ]
        result3 = v.bulk_add(dup_items)
        check("dup: stored_count == 0", len(result3["stored"]) == 0)
        check("dup: error_count == 1", len(result3["errors"]) == 1)
        check("dup: error mentions duplicate", "Duplicate" in result3["errors"][0]["message"])

        # Bulk add empty list
        result4 = v.bulk_add([])
        check("empty: stored_count == 0", len(result4["stored"]) == 0)
        check("empty: error_count == 0", len(result4["errors"]) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 8. Validation
# ------------------------------------------------------------------
def test_validation():
    print("\n=== Validation ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)

        try:
            v.add_memory("", "shared", "bio")
            check("empty text rejected", False)
        except ValueError:
            check("empty text rejected", True)

        try:
            v.add_memory("test", "invalid_scope", "bio")
            check("invalid scope rejected", False)
        except ValueError:
            check("invalid scope rejected", True)

        try:
            mid = v.add_memory("test", "shared", "custom_category")
            check("freeform category accepted", mid is not None and len(mid) > 0)
        except ValueError:
            check("freeform category accepted", False)

        try:
            v.add_memory("test", "shared", "bio", source="invalid_src")
            check("invalid source rejected", False)
        except ValueError:
            check("invalid source rejected", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 9. Injector
# ------------------------------------------------------------------
def test_injector():
    print("\n=== Injector ===")
    tmp = tempfile.mkdtemp()
    try:
        v = make_vault(tmp)
        v.add_memory("Name is Alice", "shared", "bio")
        v.add_memory("Prefers Python", "orion", "preference", ["language"])
        v.add_memory("Likes poetry", "elysia", "preference", ["writing"])

        block = build_memory_block(v, scopes=["shared", "orion"], max_items=10)
        check("block contains header", "Long-Term Memory Context" in block)
        check("block contains shared mem", "Alice" in block)
        check("block contains orion mem", "Python" in block)
        check("block excludes elysia mem", "poetry" not in block)

        empty_block = build_memory_block(v, scopes=["shared"], max_items=0)
        # max_items=0 with recall will return empty
        # Actually recall_memories with limit=0 returns empty slice
        check("empty block is empty string",
              build_memory_block(v, scopes="shared", max_items=0) == "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 10. Capacity limit
# ------------------------------------------------------------------
def test_capacity_limit():
    print("\n=== Capacity Limit ===")
    tmp = tempfile.mkdtemp()
    try:
        # Create a vault with max 3 active memories
        path = os.path.join(tmp, "vault.jsonl")
        v = MemoryVault(path, max_active=3, token_overlap_threshold=0.95)

        v.add_memory("Memory alpha", "shared", "meta")
        v.add_memory("Memory beta", "orion", "goal")
        v.add_memory("Memory gamma", "elysia", "preference")
        check("3 active at capacity", len(v.recall_memories()) == 3)

        # Fourth add should be rejected
        try:
            v.add_memory("Memory delta overflow", "shared", "meta")
            check("capacity limit enforced", False, "should have raised")
        except ValueError as e:
            check("capacity limit enforced", "full" in str(e).lower())

        # Deleting one should make room
        mems = v.recall_memories()
        v.delete_memory(mems[0].id)
        id4 = v.add_memory("Memory delta fits now", "shared", "meta")
        check("add after delete works", id4 is not None)
        check("still at capacity", len(v.recall_memories()) == 3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 11. Token-overlap duplicate detection
# ------------------------------------------------------------------
def test_token_overlap_dedup():
    print("\n=== Token-Overlap Duplicate Detection ===")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "vault.jsonl")
        v = MemoryVault(path, similarity_threshold=0.70, token_overlap_threshold=0.60)

        v.add_memory(
            "Burst mode enforces 1 tool call per tick in the runtime",
            "shared", "constraint"
        )

        # Same concept, different phrasing — token overlap should catch it
        try:
            v.add_memory(
                "In burst mode only 1 tool call is allowed per tick",
                "shared", "constraint"
            )
            check("token-overlap duplicate blocked", False, "should have raised")
        except ValueError as e:
            check("token-overlap duplicate blocked", "Duplicate" in str(e))

        # Genuinely different content with some common words — should pass
        id2 = v.add_memory(
            "Agent profiles define allowed tools and model configuration",
            "shared", "architecture"
        )
        check("different content allowed", id2 is not None)

        # Same concept but in different scope — should pass
        id3 = v.add_memory(
            "Burst mode enforces 1 tool call per tick in the runtime",
            "orion", "constraint"
        )
        check("same text different scope allowed", id3 is not None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 12. Vault stats
# ------------------------------------------------------------------
def test_vault_stats():
    print("\n=== Vault Stats ===")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "vault.jsonl")
        v = MemoryVault(path, max_active=50)

        stats0 = v.vault_stats()
        check("empty vault active=0", stats0["active_count"] == 0)
        check("empty vault max=50", stats0["max_active"] == 50)
        check("empty vault utilization=0", stats0["utilization_pct"] == 0)

        v.add_memory("The cat sat on a mat", "shared", "meta")
        v.add_memory("Docker containers use namespaces", "orion", "goal")
        id3 = v.add_memory("Parallel lines never intersect", "shared", "preference")

        stats1 = v.vault_stats()
        check("3 active", stats1["active_count"] == 3)
        check("utilization=6%", stats1["utilization_pct"] == 6.0)
        check("shared=2 in by_scope", stats1["by_scope"].get("shared") == 2)
        check("orion=1 in by_scope", stats1["by_scope"].get("orion") == 1)
        check("raw_lines=3", stats1["raw_lines"] == 3)

        # Delete one → deleted_count goes up, active goes down
        v.delete_memory(id3)
        stats2 = v.vault_stats()
        check("2 active after delete", stats2["active_count"] == 2)
        check("1 deleted after delete", stats2["deleted_count"] == 1)
        check("raw_lines=4 (append-only)", stats2["raw_lines"] == 4)
        check("compactable=2", stats2["compactable_lines"] == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 13. Compact
# ------------------------------------------------------------------
def test_compact():
    print("\n=== Compact ===")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "vault.jsonl")
        v = MemoryVault(path, max_active=50)

        id1 = v.add_memory("Version one", "shared", "meta")
        v.update_memory(id1, text="Version two")
        v.update_memory(id1, text="Version three")  # 3 lines, 1 active
        id2 = v.add_memory("Keep me", "orion", "goal")
        id3 = v.add_memory("Delete me", "elysia", "preference")
        v.delete_memory(id3)  # 6 lines total, 2 active

        stats_before = v.vault_stats()
        check("6 raw lines before compact", stats_before["raw_lines"] == 6)
        check("2 active before compact", stats_before["active_count"] == 2)

        result = v.compact()
        check("compact removed 4 lines", result["lines_removed"] == 4)
        check("compact: 2 lines after", result["lines_after"] == 2)

        stats_after = v.vault_stats()
        check("2 raw lines after compact", stats_after["raw_lines"] == 2)
        check("2 active after compact", stats_after["active_count"] == 2)
        check("0 deleted after compact", stats_after["deleted_count"] == 0)
        check("bloat_ratio=1.0", stats_after["bloat_ratio"] == 1.0)

        # Verify data integrity — latest versions survived
        mems = v.recall_memories()
        texts = {m.text for m in mems}
        check("latest text survived", "Version three" in texts)
        check("keep me survived", "Keep me" in texts)
        check("deleted not present", "Delete me" not in texts)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 14. Memory tool stats & compact actions
# ------------------------------------------------------------------
def test_tool_stats_compact():
    print("\n=== Memory Tool Stats & Compact ===")
    tmp = tempfile.mkdtemp()
    try:
        import json as _json
        import src.tools.memory_tool as _mt_mod
        from src.tools.memory_tool import MemoryTool

        # Patch vault path for isolation — must patch the module-level ref
        # that MemoryTool._vault() actually calls.
        orig_ref = _mt_mod._get_vault_path
        test_path = os.path.join(tmp, "vault.jsonl")
        _mt_mod._get_vault_path = lambda: test_path

        tool = MemoryTool()

        # Add some data
        tool.execute({"action": "add", "text": "Test mem A", "scope": "shared", "category": "meta"})
        tool.execute({"action": "add", "text": "Test mem B", "scope": "orion", "category": "goal"})

        # Stats action
        stats_raw = tool.execute({"action": "stats"})
        stats = _json.loads(stats_raw)
        check("stats status ok", stats["status"] == "ok")
        check("stats active=2", stats["active_count"] == 2)
        check("stats has utilization", "utilization_pct" in stats)
        check("stats has by_scope", "by_scope" in stats)
        check("stats has by_tier", "by_tier" in stats)

        # Compact action
        compact_raw = tool.execute({"action": "compact"})
        compact = _json.loads(compact_raw)
        check("compact status ok", compact["status"] == "ok")
        check("compact lines_after=2", compact["lines_after"] == 2)

        # Restore
        _mt_mod._get_vault_path = orig_ref
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 16. Write-gate: rejects journal-only noise
# ------------------------------------------------------------------
def test_write_gate():
    print("\n=== Write Gate ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp)

        # Should reject text with journal-only signal
        try:
            vault.add_memory("tick marker for burst 5", "shared", "meta")
            check("rejects tick marker", False, "should have raised")
        except ValueError as e:
            check("rejects tick marker", "journal-only signal" in str(e))

        try:
            vault.add_memory("routine scan complete, nothing to report", "shared", "meta")
            check("rejects nothing to report", False, "should have raised")
        except ValueError as e:
            check("rejects nothing to report", "journal-only signal" in str(e))

        # Should reject log tier
        try:
            vault.add_memory("some log entry", "shared", "meta", tier="log")
            check("rejects log tier", False, "should have raised")
        except ValueError as e:
            check("rejects log tier", "journal-only" in str(e))

        # Should reject text over max length
        try:
            vault.add_memory("x" * 1300, "shared", "meta")
            check("rejects long text", False, "should have raised")
        except ValueError as e:
            check("rejects long text", "too long" in str(e))

        # Should allow normal text
        mid = vault.add_memory("Creator's favorite color is blue", "shared", "bio")
        check("allows normal text", mid is not None and len(mid) > 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 17. Tier and topic_id fields
# ------------------------------------------------------------------
def test_tier_topic():
    print("\n=== Tier & Topic ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp)

        # Canon tier (default)
        mid1 = vault.add_memory("Mission: stabilize the runtime", "shared", "mission")
        mem1 = vault._resolve_latest()[mid1]
        check("default tier is canon", mem1.tier == "canon")
        check("no topic_id by default", mem1.topic_id is None)

        # Register tier with topic_id
        mid2 = vault.add_memory(
            "Current projects: Forge dashboard, memory upgrade",
            "shared", "project",
            tier="register", topic_id="current_projects",
        )
        mem2 = vault._resolve_latest()[mid2]
        check("register tier set", mem2.tier == "register")
        check("topic_id set", mem2.topic_id == "current_projects")

        # Upsert: adding another register with same topic_id should update
        mid3 = vault.add_memory(
            "Current projects: Forge dashboard, memory upgrade, email integration",
            "shared", "project",
            tier="register", topic_id="current_projects",
        )
        check("upsert returns same id", mid3 == mid2)
        mem3 = vault._resolve_latest()[mid2]
        check("upsert increments version", mem3.version == 2)
        check("upsert updates text", "email integration" in mem3.text)

        # to_dict / from_dict roundtrip preserves tier and topic_id
        d = mem3.to_dict()
        check("to_dict has tier", d["tier"] == "register")
        check("to_dict has topic_id", d["topic_id"] == "current_projects")
        restored = Memory.from_dict(d)
        check("from_dict preserves tier", restored.tier == "register")
        check("from_dict preserves topic_id", restored.topic_id == "current_projects")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 18. update_by_topic
# ------------------------------------------------------------------
def test_update_by_topic():
    print("\n=== Update By Topic ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp)

        # First call creates new
        mem1 = vault.update_by_topic(
            "top_priorities", "shared",
            "1) Memory upgrade  2) Stabilize burst mode",
            category="goal",
        )
        check("creates new register", mem1.version == 1)
        check("has topic_id", mem1.topic_id == "top_priorities")
        check("tier is register", mem1.tier == "register")

        # Second call updates existing
        mem2 = vault.update_by_topic(
            "top_priorities", "shared",
            "1) Memory upgrade  2) Email integration  3) Stabilize burst",
        )
        check("updates same id", mem2.id == mem1.id)
        check("version bumped", mem2.version == 2)
        check("text updated", "Email integration" in mem2.text)

        # Different scope creates new
        mem3 = vault.update_by_topic(
            "top_priorities", "orion",
            "1) Self-reflection  2) Drift control",
            category="goal",
        )
        check("different scope = new record", mem3.id != mem1.id)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 19. Consolidation candidates
# ------------------------------------------------------------------
def test_consolidation_candidates():
    print("\n=== Consolidation Candidates ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp, threshold=0.95)  # high threshold to avoid dup rejection

        vault.add_memory("Creator likes to code in Python and build agent systems", "shared", "bio")
        vault.add_memory("Creator enjoys coding in Python for agent runtime systems", "shared", "bio")
        vault.add_memory("Cats are cute animals", "shared", "other")

        pairs = vault.find_consolidation_candidates("shared", similarity_floor=0.40)
        check("finds similar pair", len(pairs) >= 1)
        if pairs:
            a, b, score = pairs[0]
            check("score is reasonable", 0.4 <= score <= 1.0)
            # The two Python/agent texts should be the most similar
            check("correct pair found",
                  ("Python" in a.text and "Python" in b.text))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 20. Propose deletions
# ------------------------------------------------------------------
def test_propose_deletions():
    print("\n=== Propose Deletions ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp, threshold=0.95)

        # Short low-value register
        vault.add_memory("ok noted", "shared", "other", tier="register")
        # Normal canon
        vault.add_memory("Creator is the creator and operator of the agent runtime", "shared", "bio")

        proposals = vault.propose_deletions("shared")
        check("proposes short text deletion", len(proposals) >= 1)
        if proposals:
            check("reason mentions short", "short" in proposals[0]["reason"].lower()
                  or "short" in str(proposals).lower())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 21. Promote to canon
# ------------------------------------------------------------------
def test_promote():
    print("\n=== Promote to Canon ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp)

        mid = vault.add_memory(
            "Current plan: stabilize and upgrade memory",
            "shared", "plan", tier="register",
        )
        mem = vault._resolve_latest()[mid]
        check("starts as register", mem.tier == "register")

        promoted = vault.promote_to_canon(
            mid,
            "CANON: Stabilize runtime and upgrade memory system as permanent mission objective",
            tags=["mission", "permanent"],
        )
        check("promoted to canon", promoted.tier == "canon")
        check("version bumped", promoted.version == 2)
        check("source is promotion", promoted.source == "promotion")
        check("text updated", "permanent mission" in promoted.text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 22. Snapshot
# ------------------------------------------------------------------
def test_snapshot():
    print("\n=== Snapshot ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp)

        # Add canon
        vault.add_memory("Mission: stabilize the runtime", "shared", "mission", tier="canon")
        # Add register with topic
        vault.add_memory(
            "Active projects: dashboard, memory",
            "shared", "project",
            tier="register", topic_id="current_projects",
        )
        # Add register without topic (should NOT appear in snapshot)
        vault.add_memory("Some misc register note", "shared", "other", tier="register")

        snapshot = vault.build_snapshot("shared")
        check("snapshot not empty", len(snapshot) > 0)
        check("has canon section", "Canon" in snapshot)
        check("has registers section", "Active Registers" in snapshot)
        check("includes canon text", "stabilize" in snapshot)
        check("includes topic register", "current_projects" in snapshot)
        check("excludes no-topic register", "misc register" not in snapshot)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 23. Stats includes tier breakdown
# ------------------------------------------------------------------
def test_stats_tiers():
    print("\n=== Stats Tier Breakdown ===")
    tmp = tempfile.mkdtemp()
    try:
        vault = make_vault(tmp)
        vault.add_memory("Canon fact", "shared", "bio", tier="canon")
        vault.add_memory("Register state", "shared", "project", tier="register", topic_id="t1")

        stats = vault.vault_stats()
        check("has by_tier", "by_tier" in stats)
        check("canon count", stats["by_tier"].get("canon", 0) == 1)
        check("register count", stats["by_tier"].get("register", 0) == 1)
        check("has register_topics", stats["register_topics"] == 1)
        check("has by_category", "by_category" in stats)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# 24. Backward compatibility: old records without tier/topic_id
# ------------------------------------------------------------------
def test_backward_compat():
    print("\n=== Backward Compatibility ===")
    tmp = tempfile.mkdtemp()
    try:
        import json as _json
        path = os.path.join(tmp, "vault.jsonl")
        # Write an old-format record (no tier, no topic_id)
        old_record = {
            "id": "old123",
            "text": "Some old memory from before the upgrade",
            "scope": "shared",
            "category": "bio",
            "tags": ["legacy"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": None,
            "source": "tool",
            "deleted_at": None,
            "version": 1,
        }
        with open(path, "w") as f:
            f.write(_json.dumps(old_record) + "\n")

        vault = MemoryVault(path)
        active = vault._read_active()
        check("reads old record", len(active) == 1)
        check("defaults tier to canon", active[0].tier == "canon")
        check("defaults topic_id to None", active[0].topic_id is None)
        check("text preserved", "old memory" in active[0].text)

        # Can still update old records
        updated = vault.update_memory("old123", text="Updated old memory text")
        check("update works on old", updated.version == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------
# Run all
# ------------------------------------------------------------------
if __name__ == "__main__":
    test_add_recall()
    test_scoping()
    test_duplicates()
    test_pii()
    test_search()
    test_update()
    test_delete()
    test_bulk_delete()
    test_bulk_add()
    test_validation()
    test_injector()
    test_capacity_limit()
    test_token_overlap_dedup()
    test_vault_stats()
    test_compact()
    test_tool_stats_compact()
    # New AGI-like memory tests
    test_write_gate()
    test_tier_topic()
    test_update_by_topic()
    test_consolidation_candidates()
    test_propose_deletions()
    test_promote()
    test_snapshot()
    test_stats_tiers()
    test_backward_compat()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)
    else:
        print("All tests passed.")
