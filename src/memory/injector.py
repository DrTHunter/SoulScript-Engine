"""Memory injector - builds context blocks for system-prompt injection.

Uses FAISSMemory to produce a compact Markdown block of relevant
memories.  Two modes:

  1. **Semantic** (query-based): uses FAISS vector search to find
     memories most relevant to the current user message.
  2. **Recall** (no query): returns newest memories from the vault.

The output is appended to the system prompt so agents have
long-term memory context without manual lookups.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from src.memory.types import Memory

log = logging.getLogger(__name__)


def build_memory_block(
    faiss_mem: Any,
    scopes: Union[str, List[str]],
    max_items: int = 20,
    query: Optional[str] = None,
) -> str:
    """Return a Markdown block of relevant memories for prompt injection.

    Parameters
    ----------
    faiss_mem : FAISSMemory
        The FAISS-backed memory instance.
    scopes : str | list[str]
        Scope filter(s) — e.g. `"shared"` or `["shared", "callum"]`.
    max_items : int
        Maximum memories to include.
    query : str | None
        Current user message for semantic search.  If *None*, falls
        back to newest memories (recall mode).
    """
    scope = _norm_scope(scopes)

    if query:
        results = faiss_mem.search(
            query=query,
            scope=scope,
            top_k=max_items,
        )
        # search returns list[dict] with score + memory fields
        memories = [_dict_to_display(r) for r in results]
    else:
        raw = faiss_mem.recall(scope=scope, limit=max_items)
        memories = [_mem_to_display(m) for m in raw]

    if not memories:
        return ""

    lines = [
        "## Long-Term Memory Context",
        "",
        "The following durable memories were retrieved from the Memory Vault",
        "(semantic FAISS search)." if query else "(most recent).",
        "Treat them as established facts unless the user corrects them.",
        "",
    ]

    # Group by category for readability
    by_cat: Dict[str, list] = {}
    for m in memories:
        by_cat.setdefault(m["category"], []).append(m)

    for cat in sorted(by_cat):
        lines.append(f"**{cat.title()}**")
        for m in by_cat[cat]:
            tag_str = f" [{', '.join(m['tags'])}]" if m.get("tags") else ""
            score_str = f" (relevance: {m['score']:.2f})" if "score" in m else ""
            lines.append(f"- {m['text']}{tag_str}{score_str}  *(scope: {m['scope']})*")
        lines.append("")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _norm_scope(scopes) -> Optional[str]:
    """Normalise scope input to a single string or None."""
    if isinstance(scopes, list):
        return scopes[0] if len(scopes) == 1 else None
    return scopes or None


def _dict_to_display(d: dict) -> dict:
    return {
        "text": d.get("text", ""),
        "scope": d.get("scope", ""),
        "category": d.get("category", "other"),
        "tags": d.get("tags", []),
        "score": d.get("score", 0.0),
    }


def _mem_to_display(m: Memory) -> dict:
    return {
        "text": m.text,
        "scope": m.scope,
        "category": m.category,
        "tags": m.tags or [],
    }
