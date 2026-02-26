# SoulScript Engine

A framework for constructing persistent AI identities. Each agent gets a layered identity stack — profile, system prompt, directives, soul script, and a durable memory vault — so personality, knowledge, and behavioral boundaries survive across sessions.

The web dashboard lets you chat with agents, manage their memories, attach knowledge notes, and configure API connections — all from a browser.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.11+** | 3.12 works too. Not tested on 3.10. |
| **pip** | Comes with Python. |
| **Git** | To clone the repo. |
| **An LLM API key** | OpenAI, Anthropic, or DeepSeek. At least one is required. |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/DrTHunter/SoulScript-Engine.git
cd SoulScript-Engine
```

### 2. Create a virtual environment (recommended)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, FAISS-cpu, Sentence-Transformers, and everything else the engine needs. The first run will download the `all-mpnet-base-v2` embedding model (~420 MB) automatically.

---

## Configuration

### Adding an API Key (Required)

The engine needs at least one LLM API key to function. There are two ways to provide one:

#### Option A — Through the Web UI (easiest)

1. Start the server (see below).
2. Open `http://localhost:8585/settings` in your browser.
3. Go to the **Connections** tab.
4. Click **Add Connection** and fill in:
   - **Name** — anything you like (e.g. "OpenAI")
   - **Type** — `external`
   - **Provider** — `openai`, `anthropic`, or `deepseek`
   - **API Key** — your key
   - **Base URL** — leave default or enter a custom endpoint
5. **Enable** the connection and assign it to one or more agents.

The key is stored locally in `config/connections.json` (this file is git-ignored and never committed).

#### Option B — Environment variables

Set one or more of these before starting the server:

```bash
# Linux / macOS
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."

# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:DEEPSEEK_API_KEY = "sk-..."
```

The LLM client checks the profile's `provider` field and looks up the matching environment variable automatically.

### Agent Profiles

Each agent is defined by a YAML file in `profiles/`. The profile sets the model, provider, temperature, allowed tools, memory scopes, and more. Example:

```yaml
name: codex_animus
provider: openai
model: gpt-4o
temperature: 0.7
system_prompt: codex_animus.system.md
memory:
  enabled: true
  scopes: [shared, codex_animus]
```

You can create new agents by adding a profile YAML, a system prompt in `prompts/`, and optionally a directive and note file.

---

## Running the Server

```bash
# Start the web dashboard
python -m uvicorn web.app:app --host 0.0.0.0 --port 8585
```

Then open **http://localhost:8585** in your browser.

### Running on a remote server

If you're deploying to a VPS or cloud instance:

```bash
# Bind to all interfaces so it's reachable externally
python -m uvicorn web.app:app --host 0.0.0.0 --port 8585
```

Make sure port **8585** is open in your firewall / security group. For production use, put it behind a reverse proxy (nginx, Caddy) with HTTPS.

### Running in the background (Linux)

```bash
nohup python -m uvicorn web.app:app --host 0.0.0.0 --port 8585 &
```

Or use `systemd`, `supervisord`, or `screen`/`tmux` to keep it alive.

---

## Project Layout

```
SoulScript-Engine/
├── web/                  # FastAPI web dashboard (app.py, templates, static)
├── src/
│   ├── llm_client/       # LLM provider abstraction (OpenAI, Anthropic, DeepSeek)
│   ├── memory/           # Memory Vault — append-only JSONL + FAISS vector search
│   ├── directives/       # Dynamic directive injection system
│   ├── governance/       # Boundary enforcement and safety rails
│   ├── tools/            # Built-in tool definitions
│   ├── routing/          # Agent routing logic
│   ├── storage/          # State + journal persistence
│   └── data_paths.py     # Canonical data directory layout
├── profiles/             # Per-agent YAML configuration
├── prompts/              # Base system prompt Markdown files
├── directives/           # Behavioral directives (always-injected)
├── notes/                # User-editable note files (always-injected)
├── data/
│   ├── memory/           # vault.jsonl + FAISS index files
│   ├── chats/            # Chat history
│   ├── user_notes/       # Knowledge notes (attachable to agents)
│   └── ...               # Journals, state, shared logs
├── config/
│   ├── settings.json     # UI and runtime preferences
│   ├── connections.json  # API keys and connections (git-ignored)
│   └── pricing.yaml      # Token cost tracking config
├── scripts/              # Utility scripts (backup, watchdog, startup)
└── tests/                # Test suite
```

## Key Concepts

### Identity Stack (5 layers)

1. **Profile** (`profiles/*.yaml`) — model, provider, temperature, tool permissions
2. **System Prompt** (`prompts/*.system.md`) — base personality and instructions
3. **Directives** (`directives/*.md`) — behavioral rules injected every turn
4. **Soul Script** — a knowledge note attached in "directive" mode that defines the agent's core identity, values, and boundaries
5. **Memory Vault** (`data/memory/vault.jsonl`) — durable, scoped, append-only memories retrieved via FAISS similarity search

### Memory Vault

- Append-only JSONL with versioning (updates and deletes create new lines)
- Two tiers: `canon` (durable) and `register` (mutable)
- Scoped per agent (`shared`, `codex_animus`, `astraea`, etc.)
- FAISS vector index for semantic retrieval using `all-mpnet-base-v2` embeddings

### Web Dashboard Pages

| Route | Purpose |
|---|---|
| `/` | Chat interface — talk to any configured agent |
| `/profiles` | View and edit agent profiles |
| `/vault` | Browse and manage the memory vault |
| `/knowledge` | Create and attach knowledge notes |
| `/settings` | Manage API connections, UI preferences |

---

## Troubleshooting

**"Port 8585 already in use"**
Kill any existing process on the port:
```bash
# Linux / macOS
lsof -ti:8585 | xargs kill -9

# Windows (PowerShell)
Get-NetTCPConnection -LocalPort 8585 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**"No API key configured"**
Make sure you've either added a connection through the Settings UI or set the appropriate environment variable (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`).

**FAISS model download is slow**
The first startup downloads `all-mpnet-base-v2` (~420 MB). This is a one-time download. If you're on a server with no internet, you can pre-download the model and place it in your Hugging Face cache directory.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
