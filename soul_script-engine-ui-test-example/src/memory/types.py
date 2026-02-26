"""Memory record type, taxonomy, and validation constants.

Memory Taxonomy (three tiers)
─────────────────────────────
CANON   – durable invariants: mission, identity, hard constraints, stable
          bio facts.  Rarely change.  Always high-priority in injection.
REGISTER – mutable state registers: one record per *topic_id*, updated in
           place (append-only version bump).  Current projects, active
           priorities, evolving preferences, agent self-state.
LOG     – ephemeral events: tick markers, runtime snapshots, check-ins,
          one-off observations.  These do NOT belong in the vault.
          The write-gate rejects LOG-tier writes.

The ``tier`` field is stored on every Memory record.  Old records
missing the field default to ``"canon"`` for backward compat.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ── Validation sets ──────────────────────────────────────────────────

def _discover_scopes() -> frozenset:
    """Build valid scopes from profile YAML files + 'shared'."""
    scopes = {"shared"}
    profiles_dir = Path(__file__).resolve().parent.parent.parent / "profiles"
    if profiles_dir.exists():
        for p in profiles_dir.glob("*.yaml"):
            scopes.add(p.stem)
    return frozenset(scopes)

VALID_SCOPES = _discover_scopes()

VALID_TIERS = frozenset({"canon", "register"})
# "log" is intentionally excluded — it must never reach the vault.

VALID_CATEGORIES = frozenset({
    # -- canon-tier categories --
    "bio", "identity", "mission", "constraint", "governance",
    # -- register-tier categories --
    "preference", "project", "goal", "health", "self_state",
    "capability", "plan",
    # -- general --
    "meta", "other",
})

VALID_SOURCES = frozenset({"chat", "manual", "tool", "operator", "promotion"})

# Phrases that almost always signal ephemeral / journal-only content.
# Used by the write-gate to auto-reject LOG-tier noise.
JOURNAL_ONLY_SIGNALS = frozenset({
    "tick marker", "runtime snapshot", "check-in", "heartbeat",
    "no changes", "nothing to report",
    "status unchanged", "routine scan", "ephemeral",
})

# Maximum text length for a single memory record (chars).
MAX_MEMORY_TEXT_LENGTH = 1200


@dataclass
class Memory:
    """A single memory record in the vault.

    New fields vs. the original schema:
    - ``tier``: "canon" | "register" — controls injection priority & lifecycle.
    - ``topic_id``: optional stable key for register-tier records so the
      agent can ``update_by_topic()`` instead of creating duplicates.
    """
    id: str
    text: str
    scope: str
    category: str
    tier: str = "canon"
    topic_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: Optional[str] = None
    source: Optional[str] = None
    deleted_at: Optional[str] = None
    version: int = 1

    def is_active(self) -> bool:
        return self.deleted_at is None

    def to_dict(self) -> Dict:
        d: Dict = {}
        d["id"] = self.id
        d["version"] = self.version
        d["created_at"] = self.created_at
        d["updated_at"] = self.updated_at
        d["tier"] = self.tier
        if self.topic_id is not None:
            d["topic_id"] = self.topic_id
        d["source"] = self.source
        d["scope"] = self.scope
        d["category"] = self.category
        d["tags"] = self.tags
        d["deleted_at"] = self.deleted_at
        d["text"] = self.text
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "Memory":
        return cls(
            id=d["id"],
            text=d["text"],
            scope=d["scope"],
            category=d["category"],
            tier=d.get("tier", "canon"),        # backward compat
            topic_id=d.get("topic_id"),
            tags=d.get("tags", []),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at"),
            source=d.get("source"),
            deleted_at=d.get("deleted_at"),
            version=d.get("version", 1),
        )
