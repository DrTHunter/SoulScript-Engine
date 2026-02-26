# directives/

User-editable directive files. Agents read these but cannot modify them.

## How It Works

Each file is plain markdown organized by `## Headings`. Each heading is a searchable section. At session start, only sections **relevant to the last conversation topic** are injected into the agent's system prompt -- the rest stay on disk and don't cost tokens.

If there's no prior conversation (fresh session), the first `max_sections` sections are loaded (default: 5).

Agents can also search directives mid-conversation using the `directives` tool (read-only: `search`, `list`, `get` actions).

## Files

| File | Who Sees It |
|------|-------------|
| `shared.md` | Both Orion and Elysia |
| `orion.md` | Only Orion |
| `elysia.md` | Only Elysia |

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

In each profile YAML (`profiles/orion.yaml`, etc.):

```yaml
directives:
  enabled: true
  scopes:
    - shared
    - orion        # or elysia
  max_sections: 5  # max sections injected at session start
```

## Prompt Injection Order

1. Base system prompt (`prompts/<profile>.system.md`)
2. Long-Term Memory Context (from Memory Vault)
3. **Active Directives** (from these files)
4. User Notes (from `notes/` files)

## Key Files

- Parser: `src/directives/parser.py`
- Store + scoring: `src/directives/store.py`
- Injector: `src/directives/injector.py`
- Tool: `src/tools/directives_tool.py`
- Injection wiring: `src/loop.py` (lines 103-113)
