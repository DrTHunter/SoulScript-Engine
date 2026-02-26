# src/policy/

Boundary enforcement, capability gating, and risk logging.

## Components

| File | Purpose |
|------|---------|
| `boundary.py` | Deterministic denial payloads, risk classification, and structured event logging |

## How It Works

When the model requests a tool or capability that is not available, the runtime does **not** crash or raise. Instead it:

1. Builds a **deterministic denial payload** (returned to the model as a normal tool result so it can continue reasoning)
2. Logs a structured `boundary_request` event to an append-only JSONL file (`data/shared/boundary_events.jsonl`)

The host code is the sole authority on tool availability. The model may *request* expanded capability via the denial payload's `how_to_enable` field, but it cannot grant itself access.

## Risk Classification

Every tool/action has a baseline risk level when denied:

| Risk | Examples |
|------|----------|
| `low` | `echo`, `memory.recall`, `memory.search`, `directives.search`, `directives.list`, `directives.get` |
| `med` | `memory.add`, `memory.update`, `memory.delete`, `continuation_update` |
| `high` | `web.search`, `web.scrape`, `email.send` — external I/O and system access |

Unknown tools default to `med`.

## Key Exports

| Name | Purpose |
|------|---------|
| `classify_risk(tool_name)` | Maps a tool name → `low`/`med`/`high` |
| `build_denial(tool_name, profile, reason, ...)` | Creates a `(denial_json, BoundaryEvent)` tuple |
| `BoundaryEvent` | Dataclass with `tool_name`, `profile`, `reason`, `risk_level`, `timestamp`, etc. |
| `BoundaryLogger` | Append-only JSONL writer for boundary events at `data/shared/boundary_events.jsonl` |

## Consumers

`build_denial()` creates the payload and `BoundaryLogger.append()` persists the event.

## Tests

See `tests/test_boundary.py` — checks covering denial payloads, risk classification, and BoundaryLogger.
