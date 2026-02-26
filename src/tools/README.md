# src/tools/

Tool implementations. Each tool is a class with two methods:

- `definition()` -- returns JSON Schema for the LLM to understand the tool
- `execute(arguments)` -- runs the tool and returns a string result

## Available Tools

| Tool | File | Description |
|------|------|-------------|
| `echo` | `echo.py` | Simple echo for testing. Returns the input message. |
| `task_inbox` | `task_inbox.py` | Cross-agent task queue. `add` tasks for a profile, `next` pulls the oldest pending task, `ack` acknowledges by ID. Supports `dry_run` mode. Backed by `data/shared/task_inbox.jsonl`. |
| `continuation_update` | `continuation_update.py` | Per-agent status document. `append` adds text, `replace_section` updates a `## Section` by heading. Backed by `data/<profile>/continuation.md`. |
| `memory` | `memory_tool.py` | Read/write durable memories. `add`, `bulk_add`, `search`, `recall`, `update`, `delete`, `bulk_delete`. Backed by `data/memory/vault.jsonl`. |
| `directives` | `directives_tool.py` | Read-only access to user-authored directives. `search`, `list`, `get`, `manifest`, `changes`. Reads from `directives/*.md` and `directives/manifest.json`. |
| `runtime_info` | `runtime_info_tool.py` | Read-only runtime state snapshot: agent identity, model, provider, policy, allowed tools. On-demand diff vs last snapshot. Burst config included when in burst mode. Available even in stasis mode. |
| `creator_inbox` | `creator_inbox.py` | Agent-to-operator direct messages. `send` messages, warnings, ideas, or permission requests to Creator. Backed by `data/shared/creator_inbox.jsonl`. |
| `web_search` | `web_search.py` | Web search via SearXNG + page scraping. `search` queries SearXNG and scrapes top results, `scrape` fetches a single URL. Modes: `fast`, `normal`, `deep` with configurable page/word limits. Includes a **Knowledge Gate** that requires the agent to justify why it needs the internet before searching. Settings persisted in `config/settings.json`. |
| `email` | `email_tool.py` | Send emails via SMTP with multi-account support. `send` dispatches email (requires subject, body, recipients), `status` checks account connectivity, `accounts` lists configured accounts. Supports per-agent default accounts, user email designation, and custom signatures. Accounts managed via Dashboard or `config/settings.json`. |

## Registration

All tools are registered in `registry.py`:

```python
_ALL_TOOLS = {
    "echo": EchoTool(),
    "task_inbox": TaskInboxTool(),
    "continuation_update": ContinuationUpdateTool(),
    "memory": MemoryTool(),
    "directives": DirectivesTool(),
    "runtime_info": RuntimeInfoTool(),
    "creator_inbox": CreatorInboxTool(),
    "web_search": WebSearchTool(),
    "email": EmailTool(),
}
```

## Allowlisting

Each profile YAML has an `allowed_tools` list. Agents can only call tools on their allowlist. The `ToolRegistry` class enforces this -- `dispatch()` returns a deterministic denial payload (JSON string) for unlisted or unknown tools, allowing the model to continue reasoning.

## Adding a New Tool

1. Create `src/tools/<name>.py` with a class exposing `definition()` and `execute(arguments)`
2. Import and add to `_ALL_TOOLS` in `registry.py`
3. Add `<name>` to `allowed_tools` in the relevant profile YAMLs
