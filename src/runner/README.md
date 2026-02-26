# src/runner/

Burst Runner — bounded autonomous agent execution. Runs an agent for N ticks with no user input.

## Components

| File | Purpose |
|------|---------|
| `types.py` | Data types: `BurstConfig`, `StepAction`, `ProposedMemory`, `StepOutput`, `TickOutcome` |
| `tick.py` | Single tick execution: prompt assembly, LLM calls, tool dispatch, memory flush |
| `burst.py` | Burst-level loop: profile loading, dependency wiring, N-tick execution, metering accumulation |

## Architecture

```
CLI (src/run_burst.py)
    ↓
burst.py — run_burst(profile, burst_ticks, max_steps, stimulus)
    ↓  loads profile, creates LLMClient, wires vault/journal/boundary/narrative
    ↓
    ╔═══════════════════════════════════════╗
    ║  For each tick (0..burst_ticks-1):    ║
    ║    tick.py — run_tick(...)            ║
    ║      1. Build system prompt           ║
    ║      2. For each step (0..max_steps): ║
    ║         - Call LLM                    ║
    ║         - Parse structured JSON       ║
    ║         - If action=tool: dispatch    ║
    ║         - If action=stop: break       ║
    ║      3. Flush proposed memories       ║
    ║      4. Return TickOutcome            ║
    ╚═══════════════════════════════════════╝
    ↓
Journal append + narrative write + metering accumulate
```

## BurstConfig

Immutable configuration for a burst execution:

| Field | Default | Description |
|-------|---------|-------------|
| `profile` | (required) | Agent name |
| `burst_ticks` | 15 | Number of ticks to run |
| `max_steps_per_tick` | 3 | Max LLM calls per tick |
| `max_tool_calls_per_tick` | 2 | Max tool calls allowed per tick |
| `stimulus` | `""` | Injected into first user message |
| `allowed_tools` | 12 actions | Frozen tuple of `tool.action` strings |

### Allowed Tool Actions (12)

```
memory.recall, memory.search, memory.add, memory.bulk_add,
memory.update, memory.delete, memory.bulk_delete,
directives.search, directives.list, directives.get,
directives.manifest, directives.changes
```

## Structured Output

Each step, the model outputs JSON with one of three actions:

| Action | Description |
|--------|-------------|
| `think` | Internal reasoning, no side effects |
| `tool` | Execute a tool (requires `tool_name` and `tool_args`) |
| `stop` | End the tick (requires `stop_reason`) |

The model can also propose memories via `proposed_memories` on any step. These are buffered and flushed through the Memory Vault at end-of-tick (PII + duplicate checks apply).

## Prompt Injection Per Tick

1. Base system prompt
2. Long-Term Memory Context (relevance-filtered)
3. User Notes (static)
4. Burst-mode step protocol (structured JSON schema)
5. Tick metadata (index, stimulus)

## Journal Output

Each tick appends a JSONL line to `data/<profile>/burst_journal.jsonl`:

```json
{
  "tick_index": 0,
  "steps_taken": 2,
  "tools_used": ["memory"],
  "tool_actions": ["memory.recall"],
  "errors": [],
  "stop_reason": "Completed review",
  "outcome_summary": "Reviewed recent memories",
  "memories_proposed": 1,
  "memories_written": 1,
  "metering": { ... }
}
```

## CLI Usage

```bash
python -m src.run_burst --profile orion --burst-ticks 15 --max-steps 3
python -m src.run_burst --profile orion --stimulus "Review and consolidate your memories."
```

## Tests

See `tests/test_burst.py` (63 checks) and `src/tests/test_burst.py` (15 tests with mock clients).
