# src/

Core source code for the agent runtime. Contains all Python modules organized into subsystems.

## Top-Level Modules

| File | Purpose |
|------|---------|
| `loop.py` | Main interactive CLI entrypoint. Loads profile, builds system prompt (base + memory + directives + notes), runs conversation loop with routing, tool dispatch, metering, and saves state/summary on exit. |
| `router.py` | Rule-based keyword agent router. Routes to `orion` (code keywords) or `elysia` (creative keywords). Designed to be replaced with an LLM classifier later. |
| `runtime_policy.py` | `RuntimePolicy` dataclass with `max_iterations`, `max_wall_time_seconds`, `stasis_mode`, `tool_failure_mode`, `self_refine_steps`. Has a `check()` method that returns a reason string if limits are hit. |
| `data_paths.py` | Canonical data directory layout. Every module that reads or writes to `data/` imports paths from here. Defines per-profile paths (`state.json`, `journal.jsonl`, `narrative.md`, etc.) and shared paths (`vault.jsonl`, `boundary_events.jsonl`, `change_log.jsonl`). Auto-creates directories on access. |

## Subsystems

| Directory | Purpose |
|-----------|---------|
| `llm_client/` | LLM provider abstraction layer (OpenAI, Ollama, Anthropic) with a common `LLMClient` interface |
| `tools/` | Tool implementations, JSON Schema definitions, and registry with allowlist enforcement |
| `memory/` | Memory Vault — durable, scoped, append-only memory with PII guard and duplicate detection |
| `directives/` | Directive parser, store, injector, and manifest system for user-authored directives |
| `storage/` | State store (rolling-window), journal store (append-only JSONL), narrative writer, human diary |
| `routing/` | Tiered model routing, budget tracking, context window management, and AGI loop scheduling |
| `observability/` | Token accounting and USD cost metering for LLM calls |
| `policy/` | Boundary enforcement, capability gating, and risk logging |
| `governance/` | Anti-drift tracking (ActiveDirectives) and audit logging (ChangeLog) |

## Data Flow

```
CLI (loop.py)
    ↓
Load profile YAML → create LLMClient (factory.py)
    ↓
Build system prompt:
  1. Base prompt (prompts/<profile>.system.md)
  2. Memory context (memory/injector.py → vault.py)
  3. Directives (directives/injector.py → store.py)
  4. User notes (notes/<profile>.md)
    ↓
Conversation loop:
  User input → LLM → tool calls → dispatch (tools/registry.py) → repeat
    ↓
Routing (routing/model_router.py) → tier selection + budget gates
Context mgmt (routing/context_manager.py) → window trimming + compaction
Budget (routing/budget_tracker.py) → cost tracking + enforcement
Scheduling (routing/tick_scheduler.py) → AGI loop timing + state
    ↓
Metering (observability/metering.py) → cost tracking
Boundary checks (policy/boundary.py) → denial payloads
Governance (governance/) → directive tracking + audit log
    ↓
Persist: state (storage/), journal (storage/)
```

Each subdirectory has its own `README.md` with detailed documentation.
