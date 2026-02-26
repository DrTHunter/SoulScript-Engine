# src/tests/

Internal tests for the burst runner subsystem. These use mock LLM clients to test tick/burst execution offline without hitting any real API.

## Files

| File | Purpose |
|------|---------|
| `test_burst.py` | 15 test functions covering the burst runner with `MockClient` and `ErrorClient` |

## What's Tested

| Test | Description |
|------|-------------|
| Types construction | `BurstConfig`, `StepOutput`, `TickOutcome` creation and serialization |
| JSON parsing | Structured output parsing from LLM responses |
| Step count enforcement | Max steps per tick is respected |
| Early stop | Tick ends when model outputs `action: stop` |
| Tool call limits | `max_tool_calls_per_tick` enforcement |
| Disallowed tools | Tools not in `BurstConfig.allowed_tools` are denied |
| Memory flushing | Proposed memories are written through the vault at end-of-tick |
| PII blocking | PII guard blocks sensitive memory content |
| LLM error capture | Errors from the LLM client are captured in `TickOutcome.errors` |
| Burst continuation | Exceptions in one tick don't stop the burst |
| Prompt assembly | System prompt layers are correctly assembled |
| Journal format | JSONL output matches expected schema |

## Running

```bash
python -m src.tests.test_burst
```

## Note

The main test suites live in the top-level `tests/` directory. This `src/tests/` directory contains supplementary tests that are more tightly coupled to internal implementation details.
