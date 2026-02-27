# Simple SoulScript Engine — Download & Run Guide

A step-by-step guide to getting the SoulScript Engine web dashboard running locally.

---

## Prerequisites

| Requirement | Version |
|---|---|
| **Python** | 3.10 or newer (3.11 recommended) |
| **Git** | Any recent version |
| **OS** | Windows 10/11, macOS, or Linux |

> **First-time FAISS note:** The engine uses `sentence-transformers` with the `all-mpnet-base-v2` model (~420 MB). It downloads automatically on first launch and is cached for future runs.

---

## 1. Clone the Repository

```bash
git clone https://github.com/DrTHunter/SoulScript-Engine.git
cd SoulScript-Engine
```

---

## 2. Install Dependencies

All dependencies are listed in `requirements.txt` at the repo root.

```bash
pip install -r requirements.txt
```

**Key packages installed:**

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web server & API |
| `jinja2` | HTML templates |
| `pyyaml` | Agent profile parsing |
| `faiss-cpu` | Vector similarity search (Memory Vault + Soul Script) |
| `sentence-transformers` | Semantic embeddings for FAISS |
| `beautifulsoup4` | HTML content stripping for knowledge notes |
| `anthropic` | Anthropic API client (optional) |

---

## 3. Configure an API Connection

The engine connects to any **OpenAI-compatible** API endpoint (OpenAI, Anthropic via proxy, Ollama, LM Studio, OpenRouter, etc.).

### Option A — Configure via the UI (recommended)

1. Start the server (Step 4 below).
2. Open `http://localhost:8989/settings` in your browser.
3. Click **Add Connection** and fill in:
   - **Name** — e.g. `OpenAI`, `Ollama Local`, `OpenRouter`
   - **URL** — the base URL (e.g. `https://api.openai.com/v1` or `http://localhost:11434/v1`)
   - **API Key** — your key (leave blank for local servers)
   - **Models** — click "Fetch Models" or add manually
4. Toggle the connection **Enabled**.

### Option B — Edit JSON directly

Edit `soul_script-engine-ui-test-example/config/connections.json`:

```json
{
  "connections": [
    {
      "id": "my-conn",
      "name": "OpenAI",
      "type": "external",
      "provider": "openai",
      "url": "https://api.openai.com/v1",
      "api_key": "sk-your-key-here",
      "models": ["gpt-4o", "gpt-4o-mini"],
      "enabled": true
    }
  ],
  "agent_connections": {}
}
```

---

## 4. Start the Server

You **must** launch from inside the `soul_script-engine-ui-test-example/` folder:

```bash
cd soul_script-engine-ui-test-example
python -m uvicorn web.app:app --host 0.0.0.0 --port 8989
```

**Windows (full path):**

```powershell
cd "SoulScript-Engine\soul_script-engine-ui-test-example"
python -m uvicorn web.app:app --host 0.0.0.0 --port 8989
```

On first launch you'll see the embedding model download, then:

```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8989
```

Open **http://localhost:8989** in your browser.

---

## 5. Dashboard Pages

| Page | URL | Description |
|---|---|---|
| **Chat** | `/chat` | Talk to agents — identity layers injected automatically |
| **Profiles** | `/profiles` | Create/edit agents, system prompts, attach knowledge |
| **Vault** | `/vault` | Browse & search the persistent memory vault |
| **Knowledge** | `/knowledge` | Create notes that agents use as Soul Script or always-on context |
| **Settings** | `/settings` | Manage API connections |
| **About** | `/about` | Editable about page |

---

## Project Structure

```
soul_script-engine-ui-test-example/
├── config/          # connections.json, settings.json, config.example.yaml
├── data/            # Runtime data (chats, memory vault, user notes, uploads)
│   ├── chats/       # Saved conversations
│   ├── memory/      # vault.jsonl + FAISS indexes
│   │   └── faiss/   # Vector indexes (auto-generated)
│   ├── shared/      # Cross-agent event logs
│   ├── uploads/     # User-uploaded files
│   └── user_notes/  # Knowledge note JSON files
├── directives/      # Agent directive markdown files
├── notes/           # Agent note markdown files
├── profiles/        # Agent identity YAML files (astraea, callum, codex_animus)
├── prompts/         # System prompt markdown (*.system.md)
├── scripts/         # Utility scripts (seed_memories.py)
├── src/             # Core engine source code
│   ├── directives/  # Directive parser, injector, manifest
│   ├── governance/  # Active directive enforcement
│   ├── llm_client/  # LLM API clients (OpenAI-compat, Anthropic, Ollama)
│   ├── memory/      # FAISS memory, vault, chunker, PII guard
│   ├── observability/ # Metering & logging
│   ├── policy/      # Boundary enforcement
│   ├── storage/     # Note collection & user notes loader
│   └── tools/       # Agent tool implementations
├── tests/           # Unit tests
├── tools/           # External tool services (email, speech, search, whisper)
└── web/             # FastAPI app, templates, static assets
    ├── app.py       # Main application entry point
    ├── static/      # CSS, JS, images
    └── templates/   # Jinja2 HTML templates
```

---

## How Identity Injection Works

Every chat message passes through a **5-layer prompt assembly pipeline** before reaching the LLM:

1. **Base Prompt** — The agent's system prompt (`prompts/{agent}.system.md`)
2. **Soul Script** — FAISS semantic retrieval from directive-mode knowledge notes
3. **Always-On Knowledge** — Verbatim text from always-mode attached knowledge
4. **Memory Vault** — FAISS search over the agent's persistent memories (`vault.jsonl`)
5. **Conversation History** — Recent user/assistant turns (truncated to 30k char budget)

Agents can also **save memories** during conversation using `[MEMORY_SAVE: ...]` tags, which are automatically extracted and written to the vault.

---

## Included Agents

| Agent | Description |
|---|---|
| **Astraea** | Default agent profile |
| **Callum** | Secondary agent profile |
| **Codex Animus** | The "Creator of Souls" — meta-agent for soul script design |

Each agent has its own profile YAML, system prompt, directives, and memory scopes.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| **Port already in use** | Kill the process: `Get-NetTCPConnection -LocalPort 8989 \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` (Windows) or `lsof -ti:8989 \| xargs kill` (Mac/Linux) |
| **ModuleNotFoundError** | Make sure you `cd` into `soul_script-engine-ui-test-example/` before running uvicorn |
| **No API connection** | Add one at `/settings` — the engine needs at least one enabled connection |
| **Slow first start** | The 420 MB `all-mpnet-base-v2` model downloads once; subsequent starts are fast |
| **FAISS import error** | Run `pip install faiss-cpu` (not `faiss`) |

---

## Useful Commands

```bash
# Run tests
cd soul_script-engine-ui-test-example
python -m pytest tests/ -v

# Seed example memories into the vault
python scripts/seed_memories.py

# Start on a different port
python -m uvicorn web.app:app --host 0.0.0.0 --port 3000
```
