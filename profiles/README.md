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
