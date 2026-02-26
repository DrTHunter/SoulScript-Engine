# src/tools/

Tool implementations. Each tool is a class with two methods:

- `definition()` -- returns JSON Schema for the LLM to understand the tool
- `execute(arguments)` -- runs the tool and returns a string result

## Available Tools

| Tool | File | Description |
|------|------|-------------|
| `echo` | `echo.py` | Simple echo for testing. Returns the input message. |
| `continuation_update` | `continuation_update.py` | Per-agent status document. `append` adds text, `replace_section` updates a `## Section` by heading. Backed by `data/<profile>/continuation.md`. |
| `memory` | `memory_tool.py` | Read/write durable memories. `add`, `bulk_add`, `search`, `recall`, `update`, `delete`, `bulk_delete`. Backed by `data/memory/vault.jsonl`. |
| `directives` | `directives_tool.py` | Read-only access to user-authored directives. `search`, `list`, `get`, `manifest`, `changes`. Reads from `directives/*.md` and `directives/manifest.json`. |

## Registration

All tools are registered in `registry.py`:

```python
_ALL_TOOLS = {
    "echo": EchoTool(),
    "continuation_update": ContinuationUpdateTool(),
    "memory": MemoryTool(),
    "directives": DirectivesTool(),
}
```

## Allowlisting

Each profile YAML has an `allowed_tools` list. Agents can only call tools on their allowlist. The `ToolRegistry` class enforces this -- `dispatch()` returns a deterministic denial payload (JSON string) for unlisted or unknown tools, allowing the model to continue reasoning.

## Adding a New Tool

1. Create `src/tools/<name>.py` with a class exposing `definition()` and `execute(arguments)`
2. Import and add to `_ALL_TOOLS` in `registry.py`
3. Add `<name>` to `allowed_tools` in the relevant profile YAMLs
