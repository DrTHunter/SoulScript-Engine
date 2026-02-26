# prompts/

Base system prompt files for each agent. These define the agent's identity, personality, and core behavior.

## Files

| File | Agent |
|------|-------|
| `orion.system.md` | Orion -- precise, analytical, code-focused |
| `elysia.system.md` | Elysia -- creative, expressive, writing-focused |

## How It Works

At session start, `loop.py` loads the file specified by `system_prompt:` in the profile YAML and inserts it as the first message (`role: "system"`). This is the foundation layer -- everything else (memories, directives, notes) gets appended after it.

## Editing

Edit these files directly to change the agent's core personality and behavior. Changes take effect on the next session start.

The `system_prompt` field in each profile YAML points to the filename:

```yaml
# profiles/orion.yaml
system_prompt: orion.system.md
```

## Prompt Injection Order

1. **Base system prompt** (from these files)
2. Long-Term Memory Context
3. Active Directives
4. User Notes
