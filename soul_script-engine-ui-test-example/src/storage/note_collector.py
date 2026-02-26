"""Note collector — loads per-agent notes respecting always/directive modes.

Reads ``config/settings.json`` to determine which notes are attached
to each agent and what mode they're in:

- **always** — raw text, injected verbatim into the system prompt every session.
- **directive** — chunked soul scripts / canon notes indexed into a SEPARATE
  NotesFAISS index.  Semantically searched at runtime and injected above
  memory vault context for priority.

Two separate FAISS systems:
  1. **NotesFAISS** — immutable soul scripts & directive notes (this module)
  2. **FAISSMemory** — mutable agent-written memories (vault.jsonl)

Used by loop.py, tick.py, and the web chat path.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.storage.user_notes_loader import strip_html

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.json"

# Lazy singleton for the NotesFAISS index
_notes_faiss = None
_notes_faiss_attempted = False


def _load_settings() -> dict:
    if not _SETTINGS_PATH.exists():
        return {}
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_notes_faiss():
    """Lazy-load the NotesFAISS index singleton.  Returns None if unavailable."""
    global _notes_faiss, _notes_faiss_attempted
    if _notes_faiss_attempted:
        return _notes_faiss
    _notes_faiss_attempted = True
    try:
        from src.memory.notes_faiss import NotesFAISS
        faiss_dir = str(_PROJECT_ROOT / "data" / "memory" / "faiss")
        _notes_faiss = NotesFAISS.load(faiss_dir)
        if _notes_faiss:
            log.info("[notes] NotesFAISS loaded (%d chunks)", _notes_faiss.index.ntotal)
        else:
            log.warning("[notes] NotesFAISS index not found — directive search disabled")
    except Exception as exc:
        log.error("[notes] Failed to load NotesFAISS: %s", exc)
    return _notes_faiss


def invalidate_notes_faiss():
    """Reset the singleton so next call reloads.  Called after reindex."""
    global _notes_faiss, _notes_faiss_attempted
    _notes_faiss = None
    _notes_faiss_attempted = False


def _load_user_note_text(note_id: str) -> str:
    """Load a single user note by ID → plain text (stripped HTML)."""
    note_path = _PROJECT_ROOT / "data" / "user_notes" / f"{note_id}.json"
    if not note_path.exists():
        return ""
    try:
        with open(note_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("trashed"):
            return ""
        html = data.get("content_html", "")
        title = data.get("title", "Untitled")
        emoji = data.get("emoji", "📝")
        content = strip_html(html)
        if not content:
            return ""
        return f"### {emoji} {title}\n\n{content}"
    except Exception:
        return ""


def _load_builtin_note_text(filename: str) -> str:
    """Load a built-in .md note from the notes/ directory."""
    path = _PROJECT_ROOT / "notes" / filename
    if not path.exists():
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        lines = [ln for ln in content.splitlines()
                 if not ln.strip().startswith("<!--")]
        return "\n".join(lines).strip()
    except Exception:
        return ""


def _get_agent_note_config(agent_name: str) -> dict:
    """Return the agent's note config from settings.json."""
    settings = _load_settings()
    return settings.get("agent_configs", {}).get(agent_name, {})


def collect_notes(
    agent_name: str,
    query: Optional[str] = None,
    top_k: int = 12,
) -> Tuple[str, str]:
    """Collect notes for an agent, split by mode.

    Args:
        agent_name: Agent profile name.
        query:      Current stimulus / user message for directive FAISS search.
                    If None or empty, directive search is skipped.
        top_k:      Max directive chunks to retrieve.

    Returns
    -------
    (always_block, directive_block)
        *always_block*: Markdown block to inject verbatim (may be empty).
        *directive_block*: Markdown block with semantically retrieved soul
            script sections.  Empty string if no query or no index.
    """
    agent_cfg = _get_agent_note_config(agent_name)

    always_parts: List[str] = []
    directive_note_ids: Set[str] = set()
    directive_builtin_fns: Set[str] = set()

    # ── User notes (from web app) ──────────────────────────────────
    attached = agent_cfg.get("attached_notes", [])
    modes = agent_cfg.get("note_modes", {})

    for nid in attached:
        mode = modes.get(nid, "always")
        if mode == "always":
            text = _load_user_note_text(nid)
            if text:
                always_parts.append(text)
        elif mode == "directive":
            directive_note_ids.add(nid)

    # ── Built-in .md notes ─────────────────────────────────────────
    note_attachments = agent_cfg.get("note_attachments", {})
    for filename, info in note_attachments.items():
        if not info.get("attached", False):
            continue
        mode = info.get("mode", "always")
        if mode == "always":
            text = _load_builtin_note_text(filename)
            if text:
                always_parts.append(f"### 📄 {filename}\n\n{text}")
        elif mode == "directive":
            directive_builtin_fns.add(filename)

    # ── Format always block ────────────────────────────────────────
    always_block = ""
    if always_parts:
        always_block = (
            "## Knowledge Notes (Always Loaded)\n\n"
            + "\n\n---\n\n".join(always_parts)
        )

    # ── Directive FAISS search ─────────────────────────────────────
    directive_block = ""
    if (directive_note_ids or directive_builtin_fns) and query and query.strip():
        nf = _get_notes_faiss()
        if nf is not None:
            try:
                results = nf.search(
                    query,
                    top_k=top_k,
                    note_ids=directive_note_ids or None,
                    builtin_filenames=directive_builtin_fns or None,
                )
                if results:
                    snippets: List[str] = []
                    for chunk, score in results:
                        meta = chunk.get("metadata", {})
                        path = meta.get("section_path",
                                        meta.get("document_title", ""))
                        text = chunk["text"]
                        label = f"**{path}**" if path else ""
                        snippets.append(
                            f"{label}\n{text}" if label else text
                        )
                    directive_block = (
                        "## Relevant Knowledge (Soul Script Retrieval)\n\n"
                        "These sections were retrieved from your Soul Script / canon notes.\n"
                        "They reflect core behavioral patterns and take priority.\n\n"
                        + "\n\n---\n\n".join(snippets)
                    )
            except Exception as exc:
                log.error("[notes] NotesFAISS search error: %s", exc)

    return always_block, directive_block
