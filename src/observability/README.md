# src/observability/

Token accounting and USD cost metering for LLM calls.

## Components

| File | Purpose |
|------|---------|
| `metering.py` | Token counting, cost calculation, and pricing registry |

## Data Classes

### `TokenUsage`

Raw token counts for a single LLM call or an aggregation.

- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `is_estimated` — true when exact counts aren't available (falls back to chars/4 heuristic)
- Supports `+` operator for accumulation

### `CostBreakdown`

USD cost breakdown for a single call or aggregation.

- `input_cost`, `output_cost`, `total_cost`
- `currency` (always `"USD"`)
- Supports `+` operator for accumulation

### `Metering`

Combined container holding both `TokenUsage` and `CostBreakdown`, plus `provider` and `model` metadata. Also supports `+` for session-level accumulation.

## Key Functions

| Function | Purpose |
|----------|---------|
| `meter_response(response, provider, messages)` | Creates a `Metering` from an `LLMResponse`. Uses exact token counts when available, otherwise estimates via chars/4. |
| `get_price(provider, model)` | Looks up per-million-token pricing from `config/pricing.yaml`. Supports exact match → prefix match (e.g. `gpt-5.2` matches `gpt-5.2-2025-12-11`) → `_default` per provider. |
| `compute_cost(usage, provider, model)` | Builds a `CostBreakdown` from token counts and pricing. |
| `zero_metering()` | Returns a zeroed `Metering` instance for initializing session accumulators. |

## Pricing Configuration

Pricing is defined in `config/pricing.yaml`:

```yaml
openai:
  gpt-5.2:
    input: 2.50    # USD per 1M input tokens
    output: 10.00  # USD per 1M output tokens
  _default:
    input: 3.00
    output: 15.00

ollama:
  _default:
    input: 0.0
    output: 0.0
```

## Usage

```python
from src.observability.metering import meter_response, zero_metering

m = meter_response(response, provider="openai", messages=messages)
session = zero_metering()
session = session + m  # accumulate across calls
```
