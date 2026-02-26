# prompts/

Base system prompt files for each agent. These define the agent's identity, personality, and core behavior.

## Files

| File | Agent |
|------|-------|
| `astraea.system.md` | Astraea — sharp, no-nonsense digital mind |
| `callum.system.md` | Callum — legacy AI / guardian construct |
| `codex_animus.system.md` | Codex Animus — AI architect, system designer |

## How It Works

The web dashboard loads the file specified by `system_prompt:` in the profile YAML and inserts it as the foundation of the system message. Everything else (soul script, knowledge, memories) gets layered on top.

## Editing

Edit these files directly to change the agent's core personality and behavior. Changes take effect on the next chat session.

The `system_prompt` field in each profile YAML points to the filename:

```yaml
# profiles/codex_animus.yaml
system_prompt: codex_animus.system.md
```

## Prompt Injection Order

1. **Base system prompt** (from these files)
2. Soul Script (agent identity layer)
3. Always-On Knowledge (attached notes)
4. Memory Vault (FAISS semantic search)
5. Conversation history
