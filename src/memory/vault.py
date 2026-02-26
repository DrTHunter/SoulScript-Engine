"""Vault Store - append-only JSONL storage backend for the FAISS memory system.

This is a pure storage layer.  Every memory record lives as a JSON line
in `data/memory/vault.jsonl`.  Adds, updates, and deletes all append a
new line - the file is never edited in place.  On read, each id resolves
to its highest-version line.

The FAISS memory system (`faiss_memory.py`) composes over this store
for semantic search and embedding management.  This module handles only
persistence, versioning, and compaction.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union
from zoneinfo import ZoneInfo

from src.memory.types import Memory
from src.memory.pii_guard import check_pii

# US Central Time - used for all vault timestamps.
_CT = ZoneInfo("America/Chicago")


def _now_ct() -> str:
    """Return the current time in US Central as an ISO string."""
    return datetime.now(_CT).isoformat()


class VaultStore:
    """Append-only JSONL storage for Memory records."""

    def __init__(self, path: str):
        self.path = path
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add(self, mem: Memory) -> None:
        """Append a memory record to the vault file."""
        self._append(mem)

    def create_memory(
        self,
        text: str,
        scope: str,
        category: str = "other",
        tags: Optional[List[str]] = None,
        source: str = "manual",
        tier: str = "canon",
        topic_id: Optional[str] = None,
    ) -> Memory:
        """Create and persist a new memory.  Returns the Memory object.

        Validates PII.  Raises ValueError on PII detection.
        """
        text = text.strip()
        if not text:
            raise ValueError("Memory text must not be empty")

        pii = check_pii(text)
        if pii:
            raise ValueError(f"PII detected - memory blocked: {'; '.join(pii)}")

        mem = Memory(
            id=uuid.uuid4().hex[:12],
            text=text,
            scope=scope.lower(),
            category=category.lower(),
            tier=tier.lower(),
            topic_id=topic_id,
            tags=tags or [],
            created_at=_now_ct(),
            source=source,
        )
        self._append(mem)
        return mem

    def update_memory(
        self,
        memory_id: str,
        text: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        tier: Optional[str] = None,
        topic_id: Optional[str] = None,
    ) -> Memory:
        """Update a memory by appending a new version.

        Returns the new version.  Raises KeyError if not found.
        """
        resolved = self.resolve_latest()
        current = resolved.get(memory_id)
        if current is None or not current.is_active():
            raise KeyError(f"Memory '{memory_id}' not found or already deleted")

        if text is not None:
            text = text.strip()
            if not text:
                raise ValueError("Memory text must not be empty")
            pii = check_pii(text)
            if pii:
                raise ValueError(f"PII detected: {'; '.join(pii)}")

        new_version = Memory(
            id=current.id,
            text=text if text is not None else current.text,
            scope=current.scope,
            category=(category.lower() if category else current.category),
            tier=(tier.lower() if tier else current.tier),
            topic_id=(topic_id if topic_id is not None else current.topic_id),
            tags=(tags if tags is not None else list(current.tags)),
            created_at=current.created_at,
            updated_at=_now_ct(),
            source=current.source,
            deleted_at=None,
            version=current.version + 1,
        )
        self._append(new_version)
        return new_version

    def delete_memory(self, memory_id: str) -> bool:
        """Soft-delete by appending a tombstone.  Returns True if found."""
        resolved = self.resolve_latest()
        current = resolved.get(memory_id)
        if current is None or not current.is_active():
            return False

        tombstone = Memory(
            id=current.id,
            text=current.text,
            scope=current.scope,
            category=current.category,
            tier=current.tier,
            topic_id=current.topic_id,
            tags=list(current.tags),
            created_at=current.created_at,
            updated_at=current.updated_at,
            source=current.source,
            deleted_at=_now_ct(),
            version=current.version + 1,
        )
        self._append(tombstone)
        return True

    def bulk_delete(self, memory_ids: List[str]) -> Dict[str, List[str]]:
        """Soft-delete multiple memories.  Returns {deleted, not_found}."""
        resolved = self.resolve_latest()
        deleted, not_found = [], []
        now = _now_ct()
        for mid in memory_ids:
            current = resolved.get(mid)
            if current is None or not current.is_active():
                not_found.append(mid)
                continue
            tombstone = Memory(
                id=current.id, text=current.text, scope=current.scope,
                category=current.category, tier=current.tier,
                topic_id=current.topic_id, tags=list(current.tags),
                created_at=current.created_at, updated_at=current.updated_at,
                source=current.source, deleted_at=now,
                version=current.version + 1,
            )
            self._append(tombstone)
            deleted.append(mid)
        return {"deleted": deleted, "not_found": not_found}

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def read_all(self) -> List[Memory]:
        """Read every raw line (all versions, including tombstones)."""
        if not os.path.exists(self.path):
            return []
        records: List[Memory] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(Memory.from_dict(json.loads(line)))
        return records

    def resolve_latest(self) -> Dict[str, Memory]:
        """Resolve each id to its highest-version record."""
        latest: Dict[str, Memory] = {}
        for m in self.read_all():
            prev = latest.get(m.id)
            if prev is None or m.version > prev.version:
                latest[m.id] = m
        return latest

    def read_active(self) -> List[Memory]:
        """Return only non-deleted latest-version records."""
        return [m for m in self.resolve_latest().values() if m.is_active()]

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a single memory by id (latest version, must be active)."""
        resolved = self.resolve_latest()
        m = resolved.get(memory_id)
        if m and m.is_active():
            return m
        return None

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def compact(self) -> Dict[str, int]:
        """Rewrite vault to only active latest versions."""
        active = sorted(
            self.read_active(),
            key=lambda m: (m.category, m.created_at),
        )
        raw_before = len(self.read_all())
        tmp_path = self.path + ".compact.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            for m in active:
                f.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp_path, self.path)
        return {
            "lines_before": raw_before,
            "lines_after": len(active),
            "lines_removed": raw_before - len(active),
        }

    def stats(self) -> Dict[str, Any]:
        """Basic storage stats."""
        resolved = self.resolve_latest()
        active = [m for m in resolved.values() if m.is_active()]
        raw_lines = len(self.read_all())
        by_scope: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_tier: Dict[str, int] = {}
        for m in active:
            by_scope[m.scope] = by_scope.get(m.scope, 0) + 1
            by_category[m.category] = by_category.get(m.category, 0) + 1
            by_tier[m.tier] = by_tier.get(m.tier, 0) + 1
        return {
            "active_count": len(active),
            "deleted_count": len(resolved) - len(active),
            "raw_lines": raw_lines,
            "by_scope": by_scope,
            "by_category": by_category,
            "by_tier": by_tier,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, mem: Memory) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(mem.to_dict(), ensure_ascii=False) + "\n")


# Backward-compat alias so existing `from src.memory.vault import MemoryVault`
# statements keep working during the transition.
MemoryVault = VaultStore
