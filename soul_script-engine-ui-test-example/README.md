# Simple SoulScript Engine — Download & Run Guide

> **Version 0.2.0** · Python 3.10+ · FastAPI + FAISS

A step-by-step guide to getting the SoulScript Engine web dashboard running locally.
Choose between the **Windows (native)** path or the **Docker** path below.

---

## Prerequisites

### Windows (native)

| Requirement | Version |
|---|---|
| **Python** | 3.10 or newer (3.11 recommended) |
| **pip** | Bundled with Python |
| **Git** | Any recent version |
| **OS** | Windows 10/11, macOS, or Linux |

### Docker

| Requirement | Version |
|---|---|
| **Docker Desktop** | 4.x or newer |
| **Docker Compose** | v2 (bundled with Docker Desktop) |
| **Git** | Any recent version |

> **First-time FAISS note:** The engine uses `sentence-transformers` with the `all-mpnet-base-v2` model (~420 MB). It downloads automatically on first launch and is cached for future runs.

---

## 1. Clone the Repository

```bash
git clone https://github.com/DrTHunter/SoulScript-Engine.git
cd SoulScript-Engine
```

---

# Windows Setup (Native Python)

## 2. Install Dependencies

All dependencies are listed in `requirements.txt` at the repo root.

```powershell
pip install -r requirements.txt
```

**Key packages installed:**

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web server & API |
| `jinja2` | HTML templates |
| `pyyaml` | Agent profile parsing |
| `httpx` | Async HTTP client (model fetching, proxy calls) |
| `faiss-cpu` | Vector similarity search (Memory Vault + Soul Script) |
| `sentence-transformers` | Semantic embeddings (`all-mpnet-base-v2`) for FAISS |
| `beautifulsoup4` | HTML content stripping for knowledge notes |
| `trafilatura` | Web content extraction |
| `anthropic` | Anthropic API client (optional) |
| `python-multipart` | File upload support |
| `markdown` | Markdown rendering |

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

## 4. Start the Server

You **must** launch from inside the `soul_script-engine-ui-test-example/` folder:

```powershell
cd soul_script-engine-ui-test-example
python -m uvicorn web.app:app --host 0.0.0.0 --port 8989
```

On first launch you'll see the embedding model download (~420 MB, cached after that), then:

```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8989
```

Open **http://localhost:8989** in your browser.

### Stopping the Server

Press `Ctrl+C` in the terminal. If the port is stuck:

```powershell
# Windows
Get-NetTCPConnection -LocalPort 8989 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

```bash
# macOS / Linux
lsof -ti:8989 | xargs kill
```

---

# Docker Setup

## 2. Build & Run

From the repo root, use the provided `Dockerfile` and `docker-compose.yml`:

```bash
cd SoulScript-Engine
docker compose up --build -d
```

This builds the image and starts the server on **http://localhost:8989**.

### `Dockerfile`

Located at `soul_script-engine-ui-test-example/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps for FAISS
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY soul_script-engine-ui-test-example/ ./soul_script-engine-ui-test-example/

WORKDIR /app/soul_script-engine-ui-test-example

EXPOSE 8989

CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8989"]
```

### `docker-compose.yml`

Located at `soul_script-engine-ui-test-example/docker-compose.yml`:

```yaml
services:
  soulscript-engine:
    build:
      context: ..
      dockerfile: soul_script-engine-ui-test-example/Dockerfile
    ports:
      - "8989:8989"
    volumes:
      # Persist runtime data between restarts
      - ./config:/app/soul_script-engine-ui-test-example/config
      - ./data:/app/soul_script-engine-ui-test-example/data
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

### Useful Docker Commands

```bash
# View logs
docker compose logs -f soulscript-engine

# Stop
docker compose down

# Rebuild after code changes
docker compose up --build -d

# Shell into the container
docker compose exec soulscript-engine bash
```

## 3. Configure an API Connection (Docker)

Same as the native setup — once the container is running, open **http://localhost:8989/settings** and add a connection.

> **Connecting to host-network services (Ollama, LM Studio):**
> Use `http://host.docker.internal:11434/v1` instead of `http://localhost:11434/v1` so the container can reach services on your host machine.

---

# Dashboard Pages

| Page | URL | Description |
|---|---|---|
| **Chat** | `/chat` | Talk to agents — identity layers injected automatically |
| **Profiles** | `/profiles` | Create/edit agents, system prompts, attach knowledge |
| **Vault** | `/vault` | Browse & search the persistent memory vault (filter by scope, category) |
| **Knowledge** | `/knowledge` | Create notes that agents use as Soul Script or always-on context |
| **Knowledge Editor** | `/knowledge/{id}/edit` | Edit a specific knowledge note |
| **Tools** | `/tools` | View available tool services |
| **Settings** | `/settings` | Manage API connections, agent configs |
| **About** | `/about` | Editable project about page |

---

## API Endpoints

<details>
<summary><strong>Chat API</strong> (7 endpoints)</summary>

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat/send` | Send message — builds 5-layer prompt, calls LLM, extracts `[MEMORY_SAVE:]` tags |
| GET | `/api/chat/history` | List all chat sessions |
| POST | `/api/chat/new` | Create a new chat session |
| GET | `/api/chat/{chat_id}` | Get a single chat |
| DELETE | `/api/chat/{chat_id}` | Delete a chat |
| PUT | `/api/chat/{chat_id}` | Update chat metadata (title, folder) |
| POST | `/api/chat/{chat_id}/title` | Auto-generate title via LLM |

</details>

<details>
<summary><strong>Profiles API</strong> (5 endpoints)</summary>

| Method | Path | Description |
|---|---|---|
| GET | `/api/profiles/{name}` | Get agent profile + config + system prompt |
| PUT | `/api/profiles/{name}` | Update agent profile/prompt/config |
| POST | `/api/profiles` | Create a new agent |
| DELETE | `/api/profiles/{name}` | Delete an agent |
| PUT | `/api/profiles/{name}/knowledge` | Update attached knowledge notes + rebuild NotesFAISS |

</details>

<details>
<summary><strong>Vault API</strong> (4 endpoints)</summary>

| Method | Path | Description |
|---|---|---|
| POST | `/api/vault/add` | Manually add a memory |
| GET | `/api/vault/stats` | Get vault statistics |
| POST | `/api/vault/delete` | Soft-delete memories by ID |
| GET | `/api/vault/compact` | Compact vault — rebuild index, purge deleted entries |

</details>

<details>
<summary><strong>Knowledge API</strong> (4 endpoints)</summary>

| Method | Path | Description |
|---|---|---|
| POST | `/api/knowledge` | Create a knowledge note |
| PUT | `/api/knowledge/{note_id}` | Update a knowledge note |
| DELETE | `/api/knowledge/{note_id}` | Soft-delete (trash) a knowledge note |
| GET | `/api/knowledge/{note_id}` | Get a single knowledge note |

</details>

<details>
<summary><strong>Connections API</strong> (5 endpoints)</summary>

| Method | Path | Description |
|---|---|---|
| GET | `/api/connections` | List all connections |
| POST | `/api/connections` | Add a connection |
| PUT | `/api/connections/{conn_id}` | Update a connection |
| DELETE | `/api/connections/{conn_id}` | Remove a connection |
| GET | `/api/connections/{conn_id}/models` | Fetch available models from the provider |
| POST | `/api/connections/probe-models` | Probe models from an unsaved connection |

</details>

<details>
<summary><strong>Other</strong></summary>

| Method | Path | Description |
|---|---|---|
| POST | `/api/about` | Update about page content |
| GET | `/api/health` | Health check (status, agents list, vault_loaded) |

</details>

---

## Project Structure

```
soul_script-engine-ui-test-example/
├── config/              # connections.json, settings.json, about.json, config.example.yaml
├── data/                # Runtime data (persisted between restarts)
│   ├── chats/           # Saved conversations (JSON per chat + index.json)
│   ├── memory/          # vault.jsonl + FAISS vector indexes
│   │   └── faiss/       # Auto-generated FAISS indexes
│   ├── shared/          # Cross-agent event logs (boundary_events.jsonl)
│   ├── uploads/         # User-uploaded files
│   └── user_notes/      # Knowledge note JSON files
├── directives/          # Agent directive markdown files + manifest.json
├── notes/               # Agent note markdown files
├── profiles/            # Agent identity YAML files
├── prompts/             # System prompt markdown (*.system.md)
├── scripts/             # Utility scripts (seed_memories.py)
├── src/                 # Core engine source code
│   ├── directives/      # Directive parser, injector, manifest, store
│   ├── governance/      # Active directive enforcement & anti-drift tracking
│   ├── llm_client/      # LLM API clients (OpenAI-compat, Anthropic, Ollama)
│   ├── memory/          # FAISS memory, vault, chunker, PII guard, notes FAISS
│   ├── observability/   # Token metering & cost tracking
│   ├── policy/          # Boundary enforcement & capability gating
│   ├── storage/         # Note collection (always-on vs directive mode) & user notes loader
│   └── tools/           # Built-in tool implementations (echo, memory, directives, continuation)
├── tests/               # Unit tests (boundary, directives, governance, memory, tools)
├── tools/               # External tool services (Docker)
│   ├── email_service/   # SMTP email relay (Python/FastAPI, port 8000)
│   ├── openedai_speech/ # Text-to-speech (Piper + XTTS, port 5050)
│   ├── searxng/         # Meta-search engine (port 3000)
│   └── whisper_stt/     # Speech-to-text (faster-whisper, port 8060)
└── web/                 # FastAPI app, templates, static assets
    ├── app.py           # Main application (1070 lines, 36 routes)
    ├── static/          # CSS (style.css)
    └── templates/       # Jinja2 HTML templates (9 pages)
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
| **Elysia** | Default agent profile |
| **Orion** | Secondary agent profile |
| **Codex Animus** | The "Creator of Souls" — meta-agent for soul script design |

Each agent has its own profile YAML, system prompt, directives, and memory scopes.
Default config: temperature 0.7, window size 50, max iterations 25, memory similarity threshold 0.85.

---

## External Tool Services (Optional)

These run as separate Docker containers and are **not required** for the core engine.

| Service | Folder | Port | Start Command |
|---|---|---|---|
| **SearXNG** (web search) | `tools/searxng/` | 3000 | `docker compose up -d` |
| **openedai-speech** (TTS) | `tools/openedai_speech/` | 5050 | `docker compose up -d` |
| **faster-whisper** (STT) | `tools/whisper_stt/` | 8060 | `docker compose up -d` |
| **Email Service** | `tools/email_service/` | 8000 | `python email_service.py` or `run_email_service.bat` |

Start any tool service by `cd`-ing into its folder and running the start command.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| **Port already in use (Windows)** | `Get-NetTCPConnection -LocalPort 8989 \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` |
| **Port already in use (Mac/Linux)** | `lsof -ti:8989 \| xargs kill` |
| **Port already in use (Docker)** | `docker compose down` then restart |
| **ModuleNotFoundError** | Make sure you `cd` into `soul_script-engine-ui-test-example/` before running uvicorn |
| **No API connection** | Add one at `/settings` — the engine needs at least one enabled connection |
| **Slow first start** | The 420 MB `all-mpnet-base-v2` model downloads once; subsequent starts are fast |
| **FAISS import error** | Run `pip install faiss-cpu` (not `faiss`) |
| **Docker can't reach Ollama** | Use `http://host.docker.internal:11434/v1` as the connection URL |
| **Docker permission errors** | Make sure Docker Desktop is running and your user is in the `docker` group (Linux) |

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
