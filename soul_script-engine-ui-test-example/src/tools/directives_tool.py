"""Directives tool — lets agents search and read user-authored directives.

Read-only: agents cannot modify directive files.
Self-contained: creates its own DirectiveStore on each call so edits
to directive files are picked up immediately.
"""

import json
import os
from typing import Any, Dict

from src.directives.store import DirectiveStore
from src.directives.manifest import load_manifest, generate_manifest, audit_changes

_BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DIRECTIVES_DIR = os.path.join(_BASE_DIR, "directives")


class DirectivesTool:
    """Read-only tool exposing directive search to agents."""

    @staticmethod
    def definition() -> Dict[str, Any]:
        return {
            "name": "directives",
            "description": (
                "Search and read user-authored directives. Directives contain "
                "structured instructions, protocols, and context organized by "
                "headings. Use 'search' to find relevant sections by keyword, "
                "'list' to see all available headings, or 'get' to read a "
                "specific section by heading name. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search", "list", "get", "manifest", "changes"],
                        "description": (
                            "'search' finds relevant sections by query, "
                            "'list' shows all headings, "
                            "'get' returns a specific section by heading, "
                            "'manifest' returns the full directives manifest "
                            "(IDs, versions, hashes, status, token estimates), "
                            "'changes' diffs live directives against the persisted "
                            "manifest and returns added/removed/changed entries."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (required for 'search').",
                    },
                    "heading": {
                        "type": "string",
                        "description": "Exact section heading (for 'get').",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Limit to a specific scope. Omit to search all.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results for 'search'. Default 5.",
                    },
                },
                "required": ["action"],
            },
        }

    @staticmethod
    def execute(arguments: Dict[str, Any]) -> str:
        action = arguments.get("action", "")
        scope = arguments.get("scope")

        if scope:
            scopes = ["shared", scope.lower()] if scope.lower() != "shared" else ["shared"]
        else:
            # Discover all scopes from profile YAML files
            from src.directives.manifest import SCOPES
            scopes = list(SCOPES)

        store = DirectiveStore(_DIRECTIVES_DIR, scopes=scopes)

        if action == "search":
            query = arguments.get("query", "")
            if not query:
                return json.dumps({"status": "error", "message": "query is required for search"})
            limit = arguments.get("limit", 5)
            results = store.search(query, limit=limit)
            return json.dumps({
                "status": "ok",
                "count": len(results),
                "sections": [
                    {"heading": s.heading, "body": s.body, "scope": s.scope}
                    for s in results
                ],
            })

        elif action == "list":
            headings = store.list_headings()
            return json.dumps({
                "status": "ok",
                "count": len(headings),
                "headings": headings,
            })

        elif action == "get":
            heading = arguments.get("heading", "")
            if not heading:
                return json.dumps({"status": "error", "message": "heading is required for get"})
            section = store.get_section(heading)
            if section is None:
                return json.dumps({"status": "not_found", "message": f"No section '{heading}'"})
            return json.dumps({
                "status": "ok",
                "heading": section.heading,
                "body": section.body,
                "scope": section.scope,
            })

        elif action == "manifest":
            # Try persisted manifest first, fall back to live generation
            manifest = load_manifest()
            if manifest is None:
                manifest = generate_manifest()
            # Optionally filter by scope
            directives = manifest.get("directives", [])
            if scope:
                target_scopes = {"shared", scope.lower()} if scope.lower() != "shared" else {"shared"}
                directives = [d for d in directives if d["scope"] in target_scopes]
            return json.dumps({
                "status": "ok",
                "manifest_version": manifest.get("manifest_version"),
                "generated_utc": manifest.get("generated_utc"),
                "hash_algo": manifest.get("hash_algo"),
                "count": len(directives),
                "directives": directives,
            })

        elif action == "changes":
            diff = audit_changes()
            return json.dumps({
                "status": "ok",
                "total_added": diff["total_added"],
                "total_removed": diff["total_removed"],
                "total_changed": diff["total_changed"],
                "unchanged_count": diff["unchanged_count"],
                "added": diff["added"],
                "removed": diff["removed"],
                "changed": diff["changed"],
            })

        else:
            return json.dumps({"status": "error", "message": f"Unknown action '{action}'"})
