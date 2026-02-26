````markdown
# src/routing/

Tiered model routing, budget tracking, context window management, and AGI loop scheduling. Routes LLM calls through a cost-optimized tier ladder and enforces spending limits.

## Files

| File | Purpose |
|------|---------|
| `model_router.py` | Tiered model routing with task classification, escalation, and budget gates |
| `budget_tracker.py` | Monthly/session/tick spending enforcement with soft and hard limits |
| `context_manager.py` | Rolling-window context trimming, working set persistence, periodic compaction |
| `tick_scheduler.py` | Indefinite/finite loop scheduler for AGI-like autonomous execution |

## Tier Ladder

Routes to the cheapest tier that can handle the task, escalating only when needed:

| Tier | Name | Default Model | Cost |
|------|------|---------------|------|
| T0 | `local_cheap` | Ollama `qwen2.5:7b` | ~$0/call |
| T1 | `local_strong` | Ollama `llama3:70b` | ~$0/call |
| T2 | `cheap_cloud` | DeepSeek `deepseek-chat` | ~$0.001/call |
| T3 | `expensive_cloud` | OpenAI `gpt-5.2` | ~$0.01–0.10/call |

## Task Classification

The router classifies tasks by keyword analysis:

| Task Type | Minimum Tier | Keywords |
|-----------|-------------|----------|
| `memory_ops` | T0 local_cheap | remember, recall, memory, vault |
| `reflection` | T0 local_cheap | reflect, introspect, journal |
| `summarization` | T0 local_cheap | summarize, recap, tldr |
| `general` | T0 local_cheap | (default fallback) |
| `planning` | T1 local_strong | plan, strategy, architecture |
| `coding` | T2 cheap_cloud | code, debug, function, refactor |
| `high_stakes` | T2 cheap_cloud | critical, production, deploy |
| `final_polish` | T3 expensive_cloud | final review, ship it, release |

Task-to-tier mapping is overridable in the profile YAML under `routing.task_overrides`.

## Routing Algorithm

1. Classify the task type from prompt text and context
2. Start at the minimum tier for that task class
3. If the same error repeats 3+ times (stuck loop), escalate one tier
4. Skip disabled tiers — escalate upwards
5. Budget gate — refuse expensive tiers if budget exceeded (hard cap → local only; soft cap → cap at cheap cloud)
6. Fallback to cheapest available tier if requested tier is unavailable

## Budget Tracking

`BudgetTracker` enforces spending limits with persistent state at `data/shared/budget_state.json`:

| Limit | Default | Behavior |
|-------|---------|----------|
| Monthly hard cap | $20.00 | Blocks all cloud tier calls |
| Monthly soft cap | $16.00 (80%) | Demotes from expensive → cheap cloud |
| Per-session cap | $2.00 | Blocks further calls in current session |
| Per-tick cap | $0.10 | Blocks individual burst tick calls |

Month rollover is automatic — spending resets on the first call of each new month.

## Context Management

`ContextManager` controls context window size for each tier:

| Tier | Token Budget |
|------|-------------|
| `local_cheap` | 4,000 tokens |
| `local_strong`, `cheap_cloud` | 16,000 tokens |
| `expensive_cloud` | 64,000 tokens |

Features:
- **Rolling window:** Keeps the system message + last N messages (default 30)
- **Auto-trim:** If token count exceeds the budget, drops oldest messages
- **Periodic compaction:** Every N ticks (default 10), older messages are summarized
- **Working set:** Hot state (objectives, decisions, errors, summaries) persisted to `data/<profile>/working_set.json`

## Tick Scheduler (AGI Loop)

`TickScheduler` manages autonomous agent execution on a configurable schedule:

- **Interval:** Configurable hours + minutes between cycles (default: 30 min)
- **Loop count:** Finite or infinite (0 = infinite)
- **Controls:** Start / stop / pause / resume
- **Auto-pause:** On budget exhaustion or consecutive error streaks
- **State persistence:** Survives restarts via `data/shared/agi_loop_state.json`
- **Thread-based:** Runs in a background thread with event-driven pause/stop

## Configuration

All settings live in the profile YAML (`profiles/<name>.yaml`):

```yaml
routing:
  enabled: true
  task_overrides:
    coding: cheap_cloud
    summarization: local_cheap
  tiers:
    local_cheap:
      provider: ollama
      model: qwen2.5:7b
      base_url: http://localhost:11434
      max_output_tokens: 2048
      max_iterations: 8
      enabled: true
    # ... (local_strong, cheap_cloud, expensive_cloud)

budget:
  monthly_hard_cap: 20.00
  monthly_soft_cap: 16.00
  per_session_cap: 2.00
  per_tick_cap: 0.10

context:
  window_size: 30
  compaction_interval: 10
  budget:
    small: 4000
    moderate: 16000
    large: 64000

agi_loop:
  interval_hours: 0
  interval_minutes: 30
  max_loops: 0
  ticks_per_loop: 15
  max_steps_per_tick: 3
  stimulus: ""
  auto_pause_on_budget: true
  auto_pause_on_error_streak: 5
```

## Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `ModelRouter` | `model_router.py` | Routes calls through tier ladder, manages LLM clients |
| `BudgetTracker` | `budget_tracker.py` | Tracks and enforces spending limits |
| `ContextManager` | `context_manager.py` | Manages context window and working set |
| `TickScheduler` | `tick_scheduler.py` | Schedules autonomous execution loops |
| `Tier` | `model_router.py` | IntEnum for tier levels (0–3) |
| `TaskType` | `model_router.py` | Task type constants for classification |
| `ContextBudget` | `context_manager.py` | Token budget limits per tier |
| `WorkingSet` | `context_manager.py` | Hot state object with objectives, decisions, errors |
| `ScheduleConfig` | `tick_scheduler.py` | AGI loop schedule parameters |

## Tests

See `tests/test_routing.py` — 44 unittest checks covering task classification, tier routing, escalation, budget enforcement, context trimming, working set management, and scheduler behavior.

````
