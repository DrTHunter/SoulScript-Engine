# notes/

User-editable note files. Contents are injected **statically** into the agent's system prompt at every session start -- no filtering, no relevance scoring. Use these for short, always-relevant context.

For longer structured content that should only load when relevant, use `directives/` instead.

## Two Note Systems

### 1. Markdown Notes (this folder)
Simple `.md` files for quick, always-on context. Edit directly in any text editor.

### 2. JSON User Notes (`data/user_notes/`)
Rich notes created via the web app with formatting, sections, and metadata. Automatically loaded and injected alongside markdown notes. Non-trashed notes are included in every session.

## Markdown Note Files

| File | Who Sees It |
|------|-------------|
| `shared.md` | Both Orion and Elysia |
| `orion.md` | Only Orion |
| `elysia.md` | Only Elysia |

## How to Use

Open any file and write below the comment header. Everything you write gets appended to the system prompt under a `## User Notes` heading.

```markdown
<!-- Shared notes -->

Currently working on agent-runtime project.
Primary language: Python 3.11
OS: Windows 11
Prefer concise responses.
```

## Behavior

- **Empty files** (only the comment header): Nothing injected
- **Edits take effect** on the next session start
- **HTML comments** (`<!-- ... -->`) are stripped before injection
- **No relevance filtering** -- everything in the file is always sent

## Injection Order

1. Base system prompt
2. Long-Term Memory Context
3. Active Directives
4. **User Notes** (from these files)

## Key Files

- Markdown injection: `src/loop.py` (lines 125-145)
- JSON notes loader: `src/storage/user_notes_loader.py`
- Burst mode injection: `src/runner/tick.py` (_load_notes function)
