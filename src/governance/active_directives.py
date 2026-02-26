"""active_directives — runtime tracking of loaded directive sections.

Maintains an in-memory registry of which directives were actually injected
into the prompt pipeline for this session.  Exposes read-only accessors
for governance tracking.

Thread-safe for single-process use.  Stateless across sessions — each
session starts empty and populates on load.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.directives.manifest import _sha256, _estimate_tokens


# ------------------------------------------------------------------
# Active directive entry
# ------------------------------------------------------------------

class _ActiveEntry:
    __slots__ = ("id", "name", "scope", "version", "sha256", "loaded_at_utc",
                 "token_estimate")

    def __init__(
        self,
        id: str,
        name: str,
        scope: str,
        version: str,
        sha256: str,
        loaded_at_utc: str,
        token_estimate: int,
    ):
        self.id = id
        self.name = name
        self.scope = scope
        self.version = version
        self.sha256 = sha256
        self.loaded_at_utc = loaded_at_utc
        self.token_estimate = token_estimate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scope": self.scope,
            "version": self.version,
            "sha256": self.sha256,
            "loaded_at_utc": self.loaded_at_utc,
            "token_estimate": self.token_estimate,
        }


# ------------------------------------------------------------------
# Singleton tracker
# ------------------------------------------------------------------

class ActiveDirectives:
    """Session-scoped registry of directives actually loaded into the prompt."""

    _entries: List[_ActiveEntry] = []

    @classmethod
    def reset(cls) -> None:
        """Clear all entries (for tests / session start)."""
        cls._entries = []

    @classmethod
    def record(
        cls,
        heading: str,
        body: str,
        scope: str,
        *,
        manifest_entry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a directive section as actively loaded.

        If *manifest_entry* is provided, uses its id/version.
        Otherwise, generates a synthetic ID from scope + heading.
        """
        full_content = heading + "\n" + body
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if manifest_entry:
            dir_id = manifest_entry.get("id", f"{scope}.{heading}")
            version = manifest_entry.get("version", "unknown")
        else:
            from src.directives.manifest import _heading_to_id
            dir_id = _heading_to_id(scope, heading)
            version = "unknown"

        entry = _ActiveEntry(
            id=dir_id,
            name=heading,
            scope=scope,
            version=version,
            sha256=_sha256(full_content),
            loaded_at_utc=now,
            token_estimate=_estimate_tokens(full_content),
        )
        cls._entries.append(entry)
        return entry.to_dict()

    @classmethod
    def record_sections(
        cls,
        sections: list,
        manifest: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Batch-record a list of DirectiveSection objects.

        Optionally cross-references against a manifest dict for IDs/versions.
        """
        manifest_by_name: Dict[str, Dict[str, Any]] = {}
        if manifest:
            for d in manifest.get("directives", []):
                manifest_by_name[d.get("name", "")] = d

        results = []
        for section in sections:
            me = manifest_by_name.get(section.heading)
            results.append(cls.record(
                heading=section.heading,
                body=section.body,
                scope=section.scope,
                manifest_entry=me,
            ))
        return results

    @classmethod
    def list(cls) -> List[Dict[str, Any]]:
        """Return a snapshot of all active directives (read-only)."""
        return [e.to_dict() for e in cls._entries]

    @classmethod
    def ids(cls) -> List[str]:
        """Return just the IDs of active directives."""
        return [e.id for e in cls._entries]

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        """Compact summary suitable for snapshots / change logs."""
        return {
            "count": len(cls._entries),
            "ids": cls.ids(),
            "scopes": sorted({e.scope for e in cls._entries}),
            "total_tokens": sum(e.token_estimate for e in cls._entries),
        }

    @classmethod
    def count(cls) -> int:
        return len(cls._entries)
