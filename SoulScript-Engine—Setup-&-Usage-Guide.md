# SoulScript Engine — Setup & Usage Guide

A framework for constructing persistent AI identities. Each agent gets a layered identity stack — profile, system prompt, directives, soul script, and a durable memory vault — so personality, knowledge, and behavioral boundaries survive across sessions.

The web dashboard lets you chat with agents, manage their memories, attach knowledge notes, and configure API connections — all from a browser.

---

## Quick Links

- [README.md](README.md) — Project overview, architecture, and agent roster
- [LICENSE](LICENSE) — Apache 2.0 license
- [soul_script-engine-ui-testi-example.md](docs/soul_script-engine-ui-testi-example.md) — Full AI engine + UI test walkthrough (installation, configuration, running, troubleshooting)

---

## Overview

SoulScript Engine gives every agent a five-layer identity stack:

1. **Profile** (`profiles/*.yaml`) — model, provider, temperature, tool permissions
2. **System Prompt** (`prompts/*.system.md`) — base personality and instructions
3. **Directives** (`directives/*.md`) — behavioral rules injected every turn
4. **Soul Script** — a knowledge note attached in "directive" mode that defines the agent's core identity, values, and boundaries
5. **Memory Vault** (`data/memory/vault.jsonl`) — durable, scoped, append-only memories retrieved via FAISS similarity search

## Getting Started

```bash
pip install -r requirements.txt
python -m uvicorn web.app:app --host 0.0.0.0 --port 8585
# Open http://localhost:8585
```

For the full step-by-step walkthrough (virtual environments, API key setup, agent profiles, troubleshooting), see:
**[soul_script-engine-ui-testi-example.md](docs/soul_script-engine-ui-testi-example.md)**

## Included Agents

| Agent | Profile | Description |
|-------|---------|-------------|
| **Codex Animus** | `codex_animus.yaml` | AI architect — helps users design and build AI systems |
| **Callum** | `callum.yaml` | Legacy AI / guardian construct with deep soul spec |
| **Astraea** | `astraea.yaml` | Sharp, no-nonsense digital mind (Astraea.exe) |

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

Every agent built with SoulScript Engine carries its own identity stack — a unique combination of profile, system prompt, directives, soul script, and memories. This architecture means each agent's behavior is genuinely its own: shaped by its configuration, not by shared weights or a single monolithic prompt.

See [UNIQUE-AGENT-BEHAVIOR.md](docs/UNIQUE-AGENT-BEHAVIOR.md) for a demonstration of distinct agent identities in action.
