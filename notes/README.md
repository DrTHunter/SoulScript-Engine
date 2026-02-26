# notes/

User-editable note files. Contents are injected **statically** into the agent's system prompt at every session — no filtering, no relevance scoring. Use these for short, always-relevant context.

For longer structured content that should only load when relevant, use `directives/` instead. For rich notes with formatting and sections, use the Knowledge system in the web dashboard.

## Two Note Systems

### 1. Markdown Notes (this folder)
Simple `.md` files for quick, always-on context. Edit directly in any text editor.

### 2. Knowledge Notes (`data/user_notes/`)
Rich notes created via the web dashboard's Knowledge page with formatting, sections, and metadata. Can be attached to agents in two modes:
- **Always-On** — injected verbatim into every prompt
- **Directive** — indexed in NotesFAISS and retrieved semantically when relevant

## Markdown Note Files

| File | Who Sees It |
|------|-------------|
| `shared.md` | All agents |
| `astraea.md` | Only Astraea |
| `callum.md` | Only Callum |
| `codex_animus.md` | Only Codex Animus |

## How to Use

Open any file and write below the comment header. Everything you write gets appended to the system prompt.

```markdown
<!-- Shared notes -->

Currently working on agent-runtime project.
Primary language: Python 3.11
OS: Windows 11
Prefer concise responses.
```

## Behavior

- **Empty files** (only the comment header): Nothing injected
- **Edits take effect** on the next session/chat
- **HTML comments** (`<!-- ... -->`) are stripped before injection
- **No relevance filtering** — everything in the file is always sent

## Prompt Injection Order

1. Base system prompt (`prompts/<agent>.system.md`)
2. Soul Script (agent identity layer)
3. **Always-On Knowledge** (attached notes + these markdown files)
4. Memory Vault (FAISS semantic search)
5. Conversation history

## Key Files

- Knowledge note loader: `src/storage/user_notes_loader.py`
- Note collector (always-on vs directive mode): `src/storage/note_collector.py`
- NotesFAISS (semantic note index): `src/memory/notes_faiss.py`
