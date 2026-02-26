# SoulScript Engine

A framework for constructing persistent AI identities. Each agent gets a layered identity stack — profile, system prompt, directives, soul script, and a durable memory vault — so personality, knowledge, and behavioral boundaries survive across sessions.

## Quick Start

```bash
pip install -r requirements.txt
python -m web.app
# Open http://localhost:8585
```

For detailed setup see [SoulScript-Engine—Setup-&-Usage-Guide.md](SoulScript-Engine%E2%80%94Setup-%26-Usage-Guide.md).

## Architecture

```
Profile YAML ─→ LLM Client (OpenAI / Ollama / Anthropic / DeepSeek)
     │
     ▼
System Prompt Assembly:
  1. Base Prompt (prompts/<agent>.system.md)
  2. Soul Script (agent identity layer)
  3. Always-On Knowledge (attached notes)
  4. Memory Vault (FAISS semantic search + vault.jsonl)
  5. Conversation history
     │
     ▼
Web Dashboard (FastAPI + Jinja2)  ─→  Chat ─→  Tool dispatch ─→  LLM loop
```

## Included Agents

| Agent | Profile | Description |
|-------|---------|-------------|
| **Codex Animus** | `codex_animus.yaml` | AI architect — helps users design and build AI systems |
| **Callum** | `callum.yaml` | Legacy AI / guardian construct with deep soul spec |
| **Astraea** | `astraea.yaml` | Sharp, no-nonsense digital mind (Astraea.exe) |

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `data/` | Runtime data — chats, memory vault, FAISS indexes, user notes |
| `soul_script-engine-ui-test-example/` | All engine source, config, agents, web UI, and docs |

## Key Dependencies

- **Python 3.11+**
- **FastAPI + Uvicorn** — web dashboard
- **FAISS + sentence-transformers** — semantic memory search
- **Anthropic SDK** — Claude model support
- **requests + PyYAML** — API calls and configuration

See `requirements.txt` for the full list.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

Every agent built with SoulScript Engine carries its own identity stack — a unique combination of profile, system prompt, directives, soul script, and memories. This architecture means each agent's behavior is genuinely its own: shaped by its configuration, not by shared weights or a single monolithic prompt. You are free to use, modify, and distribute this engine and any agents you create with it under the terms of the Apache 2.0 license.

See [UNIQUE-AGENT-BEHAVIOR.md](soul_script-engine-ui-test-example/docs/UNIQUE-AGENT-BEHAVIOR.md) for a demonstration of distinct agent identities in action.
