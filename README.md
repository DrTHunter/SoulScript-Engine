# SoulScript-Engine (MVP)

A minimal runtime to demonstrate the Soul Script concept: chat sessions with profile-based agents, a durable memory vault, always-injected notes, and simple settings.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key (OpenAI)
set OPENAI_API_KEY=sk-your-key-here

# Run a chat session (interactive)
python -m src.loop --profile orion
python -m src.loop --profile elysia
```

## What Is Included

- Chat loop with profile-based configuration
- Durable Memory Vault (append-only, scoped)
- Notes injection (always-on context)
- Settings file for runtime and UI preferences

## Project Layout

```
SoulScript-Engine/
  src/
    loop.py              # Main CLI entrypoint and conversation loop
    data_paths.py        # Canonical data directory layout
    llm_client/          # LLM provider abstraction (OpenAI)
    memory/              # Memory Vault (durable, scoped, append-only)
    storage/             # State + journal persistence
  profiles/              # Per-agent YAML configuration
  prompts/               # Base system prompt files
  notes/                 # User-editable note files (always injected)
  data/                  # Runtime data (state, journals, vault)
  config/                # Settings file(s)
```

## Profiles

Profiles define the agent identity and model config:

- `profiles/orion.yaml`
- `profiles/elysia.yaml`

## Memory Vault

- **File:** `data/memory/vault.jsonl`
- **Append-only:** Updates and deletes append new versioned lines
- **Scoped:** `shared`, `orion`, `elysia`

The vault stores durable memories for retrieval during chat sessions.

## Notes

- **Files:** `notes/shared.md`, `notes/orion.md`, `notes/elysia.md`
- **Behavior:** Always injected at session start (no filtering)

Use notes for short, always-relevant context.

## Settings

- **File:** `config/settings.json`
- Stores runtime and UI preferences (auto-created on first save)

## Requirements

- Python 3.11+
- `requests` >= 2.28.0
- `pyyaml` >= 6.0
- Windows 11 (tested), should work on Linux/macOS
