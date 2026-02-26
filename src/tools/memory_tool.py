"""Memory tool - lets agents store, search, and manage memories
via the FAISS-backed memory system.

Architecture:
  - vault.jsonl is the durable storage (each memory = one JSONL line)
  - FAISS provides semantic (meaning-based) search over vault contents
  - This tool is the agent-facing interface to both

All writes go to vault first, then sync to FAISS index automatically.
Each memory can be individually viewed and deleted.
"""

import json
from typing import Any, Dict, List

from src.memory.faiss_memory import FAISSMemory
from src.memory.types import VALID_CATEGORIES, VALID_SCOPES, VALID_SOURCES
from src.data_paths import vault_path as _get_vault_path, faiss_dir as _get_faiss_dir


class MemoryTool:
    """Tool exposing FAISS-backed memory operations to agents."""

    def __init__(self):
        self._mem: FAISSMemory = None

    def _get_mem(self) -> FAISSMemory:
        """Lazy-create the FAISSMemory instance."""
        if self._mem is None:
            self._mem = FAISSMemory(
                vault_path=_get_vault_path(),
                faiss_dir=_get_faiss_dir(),
            )
        return self._mem

    @staticmethod
    def definition() -> Dict[str, Any]:
        return {
            "name": "memory",
            "description": (
                "Store, search, and manage durable memories. "
                "Memories persist across sessions in vault.jsonl and are "
                "searchable by meaning via FAISS vector embeddings.\n\n"
                "ACTIONS:\n"
                "- add: store a new memory (text + scope + category required)\n"
                "- remember: quick-store with sensible defaults\n"
                "- search: find memories by meaning (semantic search)\n"
                "- recall: list memories (newest first, no embedding needed)\n"
                "- get: retrieve a single memory by id\n"
                "- update: change text/category/tags on an existing memory\n"
                "- delete: soft-delete a memory by id\n"
                "- bulk_delete: soft-delete multiple memories\n"
                "- list: list all active memories\n"
                "- stats: vault + FAISS health dashboard\n"
                "- compact: remove old versions/tombstones and rebuild index\n"
                "- rebuild_index: rebuild FAISS index from vault"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "add", "remember", "search", "recall", "get",
                            "update", "delete", "bulk_delete", "list",
                            "stats", "compact", "rebuild_index",
                        ],
                        "description": "The operation to perform.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Memory content (for add/remember/update).",
                    },
                    "scope": {
                        "type": "string",
                        "enum": sorted(VALID_SCOPES),
                        "description": "Memory scope (shared, or agent-specific).",
                    },
                    "category": {
                        "type": "string",
                        "enum": sorted(VALID_CATEGORIES),
                        "description": "Memory category.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for filtering.",
                    },
                    "source": {
                        "type": "string",
                        "enum": sorted(VALID_SOURCES),
                        "description": "Origin of the memory.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query text (for search action).",
                    },
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID (for get/update/delete).",
                    },
                    "memory_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of memory IDs (for bulk_delete).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10 for search, 20 for recall/list).",
                    },
                },
                "required": ["action"],
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> str:
        action = arguments.get("action", "")
        try:
            handler = {
                "add": self._add,
                "remember": self._remember,
                "search": self._search,
                "recall": self._recall,
                "get": self._get,
                "update": self._update,
                "delete": self._delete,
                "bulk_delete": self._bulk_delete,
                "list": self._list,
                "stats": self._stats,
                "compact": self._compact,
                "rebuild_index": self._rebuild_index,
            }.get(action)
            if handler is None:
                return json.dumps({"status": "error", "message": f"Unknown action '{action}'"})
            return handler(arguments)
        except (ValueError, KeyError) as exc:
            return json.dumps({"status": "error", "message": str(exc)})

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _add(self, args: Dict[str, Any]) -> str:
        text = args.get("text", "")
        scope = args.get("scope", "")
        category = args.get("category", "")
        if not text:
            return json.dumps({"status": "error", "message": "text is required"})
        if not scope:
            return json.dumps({"status": "error", "message": "scope is required"})
        if not category:
            return json.dumps({"status": "error", "message": "category is required"})

        mem = self._get_mem().add(
            text=text,
            scope=scope,
            category=category,
            tags=args.get("tags"),
            source=args.get("source", "tool"),
            tier=args.get("tier", "register"),
            topic_id=args.get("topic_id"),
        )
        return json.dumps({
            "status": "stored",
            "id": mem.id,
            "scope": mem.scope,
            "category": mem.category,
        })

    def _remember(self, args: Dict[str, Any]) -> str:
        text = args.get("text", "")
        if not text:
            return json.dumps({"status": "error", "message": "text is required"})

        result = self._get_mem().remember(
            text=text,
            scope=args.get("scope", "shared"),
            category=args.get("category", "other"),
            source=args.get("source", "tool"),
            tags=args.get("tags"),
        )
        return json.dumps(result)

    def _search(self, args: Dict[str, Any]) -> str:
        query = args.get("query", "")
        if not query:
            return json.dumps({"status": "error", "message": "query is required"})

        results = self._get_mem().search(
            query=query,
            scope=args.get("scope"),
            category=args.get("category"),
            top_k=args.get("limit", 10),
        )
        return json.dumps({
            "status": "ok",
            "count": len(results),
            "memories": results,
        })

    def _recall(self, args: Dict[str, Any]) -> str:
        memories = self._get_mem().recall(
            scope=args.get("scope"),
            category=args.get("category"),
            tags=args.get("tags"),
            limit=args.get("limit", 20),
        )
        return json.dumps({
            "status": "ok",
            "count": len(memories),
            "memories": [self._fmt(m) for m in memories],
        })

    def _get(self, args: Dict[str, Any]) -> str:
        memory_id = args.get("memory_id", "")
        if not memory_id:
            return json.dumps({"status": "error", "message": "memory_id is required"})
        mem = self._get_mem().get(memory_id)
        if mem is None:
            return json.dumps({"status": "not_found"})
        return json.dumps({"status": "ok", "memory": self._fmt(mem)})

    def _update(self, args: Dict[str, Any]) -> str:
        memory_id = args.get("memory_id", "")
        if not memory_id:
            return json.dumps({"status": "error", "message": "memory_id is required"})

        new_ver = self._get_mem().update(
            memory_id,
            text=args.get("text"),
            category=args.get("category"),
            tags=args.get("tags"),
        )
        return json.dumps({
            "status": "updated",
            "id": new_ver.id,
            "version": new_ver.version,
        })

    def _delete(self, args: Dict[str, Any]) -> str:
        memory_id = args.get("memory_id", "")
        if not memory_id:
            return json.dumps({"status": "error", "message": "memory_id is required"})
        ok = self._get_mem().delete(memory_id)
        return json.dumps({"status": "deleted" if ok else "not_found"})

    def _bulk_delete(self, args: Dict[str, Any]) -> str:
        memory_ids = args.get("memory_ids", [])
        if not memory_ids:
            return json.dumps({"status": "error", "message": "memory_ids is required"})
        result = self._get_mem().bulk_delete(memory_ids)
        return json.dumps({
            "status": "ok",
            "deleted_count": len(result["deleted"]),
            "deleted": result["deleted"],
            "not_found": result["not_found"],
        })

    def _list(self, args: Dict[str, Any]) -> str:
        memories = self._get_mem().list_all(scope=args.get("scope"))
        limit = args.get("limit", 50)
        return json.dumps({
            "status": "ok",
            "count": len(memories[:limit]),
            "total": len(memories),
            "memories": [self._fmt(m) for m in memories[:limit]],
        })

    def _stats(self, args: Dict[str, Any]) -> str:
        return json.dumps({"status": "ok", **self._get_mem().stats()})

    def _compact(self, args: Dict[str, Any]) -> str:
        result = self._get_mem().compact()
        return json.dumps({"status": "ok", **result})

    def _rebuild_index(self, args: Dict[str, Any]) -> str:
        result = self._get_mem().rebuild_index()
        return json.dumps(result)

    @staticmethod
    def _fmt(m) -> Dict[str, Any]:
        d = {
            "id": m.id,
            "text": m.text,
            "scope": m.scope,
            "category": m.category,
            "tier": m.tier,
            "tags": m.tags,
            "source": m.source,
            "created_at": m.created_at,
            "version": m.version,
        }
        if m.topic_id:
            d["topic_id"] = m.topic_id
        return d
