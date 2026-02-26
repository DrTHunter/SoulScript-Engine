# directives/

User-editable directive files. Agents read these but cannot modify them.

## How It Works

Each file is plain markdown organized by `## Headings`. Each heading is a searchable section. At session start, only sections **relevant to the last conversation topic** are injected into the agent's system prompt — the rest stay on disk and don't cost tokens.

If there's no prior conversation (fresh session), the first `max_sections` sections are loaded (default: 5).

Agents can also search directives mid-conversation using the `directives` tool (read-only: `search`, `list`, `get` actions).

## Files

| File | Who Sees It |
|------|-------------|
| `shared.md` | All agents |
| `astraea.md` | Only Astraea |
| `callum.md` | Only Callum |
| `codex_animus.md` | Only Codex Animus |
| `manifest.json` | Auto-generated index of all directive sections |

## Format

```markdown
<!-- Optional comment header (stripped before injection) -->

## Section Heading
Content goes here. Everything under a heading until the
next heading (or end of file) is one searchable section.

## Another Section
More content here.
```

- Only `## ` (h2) headings are recognized as section delimiters
- Content before the first heading is ignored
- HTML comments (`<!-- ... -->`) are stripped
- Empty sections (heading with no body) are skipped

## Configuration

In each profile YAML (`profiles/<agent>.yaml`):

```yaml
directives:
  enabled: true
  scopes:
    - shared
    - codex_animus   # agent-specific scope
  max_sections: 5    # max sections injected at session start
```

## Prompt Injection Order

1. Base system prompt (`prompts/<agent>.system.md`)
2. Soul Script (agent identity layer)
3. Always-On Knowledge (attached notes)
4. **Memory Vault** (FAISS semantic search)
5. Conversation history

## Key Files

- Parser: `src/directives/parser.py`
- Store + scoring: `src/directives/store.py`
- Injector: `src/directives/injector.py`
- Manifest: `src/directives/manifest.py`
- Tool: `src/tools/directives_tool.py`
