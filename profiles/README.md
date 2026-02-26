# profiles/

YAML configuration files for each agent. One file per agent.

## Files

| File | Agent |
|------|-------|
| `orion.yaml` | Orion |
| `elysia.yaml` | Elysia |

## Structure

```yaml
name: orion                    # Agent name (used for scoping, file paths)
provider: openai               # LLM provider: "openai", "ollama", or "anthropic"
model: gpt-5.2                 # Model identifier
base_url: https://api.openai.com/v1  # API endpoint
temperature: 0.7               # Sampling temperature

system_prompt: orion.system.md # File in prompts/ for base personality
window_size: 50                # Max non-system messages kept in state

allowed_tools:                 # Tools this agent can call
  - echo
  - continuation_update
  - memory
  - directives

policy:                        # Runtime safety limits
  max_iterations: 25           # Max LLM calls per user turn
  # max_wall_time_seconds: 120 # Optional wall clock limit
  stasis_mode: false           # If true, blocks all tool calls
  tool_failure_mode: continue  # "continue" or "stop" on tool errors

memory:                        # Memory Vault config
  enabled: true
  scopes:                      # Which vault scopes this agent sees
    - shared
    - orion
  max_items: 20                # Max memories injected at session start
  similarity_threshold: 0.85   # Duplicate detection threshold

directives:                    # Directives config
  enabled: true
  scopes:                      # Which directive files to load
    - shared
    - orion
  max_sections: 5              # Max sections injected at session start

# ── Tiered Model Routing ──────────────────────────────────────────
routing:
  enabled: true
  task_overrides:              # Override which tier handles each task type
    coding: cheap_cloud
    summarization: local_cheap
    planning: local_strong
    high_stakes: cheap_cloud
    final_polish: expensive_cloud
    memory_ops: local_cheap
    reflection: local_cheap
  tiers:
    local_cheap:               # T0 — free local model
      provider: ollama
      model: qwen2.5:7b
      base_url: http://localhost:11434
      temperature: 0.6
      max_output_tokens: 2048
      max_iterations: 8
      enabled: true
    local_strong:              # T1 — large local model
      provider: ollama
      model: llama3:70b
      base_url: http://localhost:11434
      max_output_tokens: 4096
      max_iterations: 10
      enabled: true
    cheap_cloud:               # T2 — cheap cloud API
      provider: deepseek
      model: deepseek-chat
      base_url: https://api.deepseek.com/v1
      max_output_tokens: 8192
      max_iterations: 12
      enabled: true
    expensive_cloud:           # T3 — premium cloud API
      provider: openai
      model: gpt-5.2
      base_url: https://api.openai.com/v1
      max_output_tokens: 16384
      max_iterations: 15
      enabled: true

# ── Budget Limits ─────────────────────────────────────────────────
budget:
  monthly_hard_cap: 20.00      # Hard stop for monthly spending
  monthly_soft_cap: 16.00      # Warning threshold (tier demotion)
  per_session_cap: 2.00        # Max spend per interactive session
  per_tick_cap: 0.10           # Max spend per burst tick

# ── Context Management ────────────────────────────────────────────
context:
  window_size: 30              # Rolling window message count
  compaction_interval: 10      # Compact every N ticks
  budget:
    small: 4000                # Token limit for local_cheap
    moderate: 16000            # Token limit for local_strong / cheap_cloud
    large: 64000               # Token limit for expensive_cloud

# ── AGI Loop Defaults ─────────────────────────────────────────────
agi_loop:
  interval_hours: 0            # Hours between loops
  interval_minutes: 30         # Minutes between loops
  max_loops: 0                 # 0 = infinite
  ticks_per_loop: 15           # Burst ticks per loop cycle
  max_steps_per_tick: 3        # Max model calls per tick
  stimulus: ""                 # Default stimulus text
  auto_pause_on_budget: true   # Pause when budget is exhausted
  auto_pause_on_error_streak: 5  # Pause after N consecutive errors
```

## How to Switch Provider/Model

Change `provider`, `model`, and `base_url`:

**OpenAI:**
```yaml
provider: openai
model: gpt-5.2
base_url: https://api.openai.com/v1
```

**Ollama (local):**
```yaml
provider: ollama
model: qwen2.5:14b
base_url: http://localhost:11434
```

## Adding a New Agent

1. Create `profiles/<name>.yaml` with the structure above
2. Create `prompts/<name>.system.md` for the base personality
3. Optionally create `notes/<name>.md` and `directives/<name>.md`
4. Run with: `python -m src.loop --profile <name>`
