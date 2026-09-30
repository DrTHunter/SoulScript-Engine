# SoulScript Engine — Setup & Usage Guide

A framework for constructing persistent AI identities. Each agent gets a layered identity stack — profile, system prompt, directives, soul script, and a durable memory vault — so personality, knowledge, and behavioral boundaries survive across sessions.

The web dashboard lets you chat with agents, manage their memories, attach knowledge notes, and configure API connections — all from a browser.

---

## Quick Links

- [README.md](README.md) — Project overview, architecture, and agent roster
- [LICENSE](LICENSE) / [LICENSE.md](LICENSE.md) — dual-licensed: GNU AGPL v3.0 or a commercial license
- [example app README](soul_script-engine-ui-test-example/README.md) — Full AI engine + UI test walkthrough (installation, configuration, running, troubleshooting)

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
cd soul_script-engine-ui-test-example
python -m uvicorn web.app:app --host 127.0.0.1 --port 8989
# Open http://localhost:8989
```

For the full step-by-step walkthrough (virtual environments, API key setup, agent profiles, troubleshooting), see:
**[example app README](soul_script-engine-ui-test-example/README.md)**

## Included Agents

| Agent | Profile | Description |
|-------|---------|-------------|
| **Codex Animus** | `codex_animus.yaml` | AI architect — helps users design and build AI systems |
| **Orion** | `orion.yaml` | Legacy AI / guardian construct with deep soul spec |
| **Elysia** | `elysia.yaml` | Sharp, no-nonsense digital mind (Elysia) |

## License

Dual-licensed: **GNU AGPL v3.0** ([LICENSE](LICENSE)), free to use, modify, and self-host under copyleft terms; or the **commercial license** ([LICENSE.md](LICENSE.md)) for closed-source products, free until $100k in lifetime gross revenue, then 5% of net revenue. Custom terms: **dr_hunter@yahoo.com**.

Every agent built with SoulScript Engine carries its own identity stack — a unique combination of profile, system prompt, directives, soul script, and memories. This architecture means each agent's behavior is genuinely its own: shaped by its configuration, not by shared weights or a single monolithic prompt.

See [UNIQUE-AGENT-BEHAVIOR.md](UNIQUE-AGENT-BEHAVIOR.md) for a demonstration of distinct agent identities in action.
