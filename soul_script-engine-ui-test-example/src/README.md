# src/

Core source code for the agent runtime. Contains all Python modules organized into subsystems.

## Top-Level Modules

| File | Purpose |
|------|---------|
| `runtime_policy.py` | `RuntimePolicy` dataclass with `max_iterations`, `max_wall_time_seconds`, `stasis_mode`, `tool_failure_mode`, `self_refine_steps`. Has a `check()` method that returns a reason string if limits are hit. |
| `data_paths.py` | Canonical data directory layout. Every module that reads or writes to `data/` imports paths from here. Defines per-profile paths (`state.json`, `journal.jsonl`, `narrative.md`, etc.) and shared paths (`vault.jsonl`, `boundary_events.jsonl`, `change_log.jsonl`). Auto-creates directories on access. |

## Subsystems

| Directory | Purpose |
|-----------|---------|
| `llm_client/` | LLM provider abstraction layer (OpenAI, Ollama, Anthropic, DeepSeek) with a common `LLMClient` interface |
| `tools/` | Tool implementations and JSON Schema definitions |
| `memory/` | Memory system — FAISS semantic search backed by vault.jsonl, plus NotesFAISS for knowledge notes |
| `directives/` | Directive parser, store, injector, and manifest system for user-authored directives |
| `storage/` | Note collector (always-on vs directive mode), user notes loader, HTML stripping |
| `observability/` | Token accounting and USD cost metering for LLM calls |
| `policy/` | Boundary enforcement, capability gating, and risk logging |
| `governance/` | Anti-drift tracking (ActiveDirectives) and audit logging (ChangeLog) |

## Data Flow

```
Web Dashboard (web/app.py)
    ↓
Load profile YAML → create LLMClient (factory.py)
    ↓
Build system prompt:
  1. Base prompt (prompts/<agent>.system.md)
  2. Soul Script (agent identity layer)
  3. Always-On Knowledge (attached notes)
  4. Memory Vault (FAISS semantic search → vault.jsonl)
  5. Conversation history
    ↓
Chat loop:
  User message → LLM → tool calls → dispatch → repeat
    ↓
Boundary checks (policy/boundary.py) → denial payloads
Governance (governance/) → directive tracking + audit log
    ↓
Persist: chats (data/chats/), vault (data/memory/)
```

Each subdirectory has its own `README.md` with detailed documentation.
