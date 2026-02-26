# web/

Orion Forge — the web dashboard for the agent runtime. A full-featured browser-based control panel built with FastAPI, Jinja2, and vanilla JavaScript.

## Quick Start

```bash
python -m web.app
# Open http://localhost:8585

# Custom port / expose to network
python -m web.app --port 9000
python -m web.app --host 0.0.0.0
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI application — all routes, helpers, and API endpoints (89 handlers) |
| `static/style.css` | Stylesheet for the dashboard |
| `templates/` | Jinja2 HTML templates (15 pages) |

## Templates

| Template | Page |
|----------|------|
| `base.html` | Shared layout (nav, sidebar, footer) |
| `dashboard.html` | Home — agent overview and quick stats |
| `chat.html` | Real-time chat with agents (interactive + burst mode) |
| `vault.html` | Memory vault browser with stats, compaction, and management |
| `inbox.html` | Creator inbox — agent-to-operator messages |
| `narratives.html` | Narrative log viewer (per-agent) |
| `journals.html` | JSONL journal viewer |
| `state.html` | Conversation state inspector |
| `boundary.html` | Boundary event log |
| `profiles.html` | Agent profile viewer/editor, avatar upload, create new agents |
| `settings.html` | Timezone, display preferences, chat background |
| `tools.html` | Tool registry with detail panels and config |
| `notes_list.html` | Notes browser with folders, emoji, and AI transforms |
| `notes_trash.html` | Trash/restore for deleted notes |
| `note_editor.html` | Rich note editor |
| `agi_loop.html` | AGI loop scheduler — configure and monitor autonomous execution |

## API Endpoints (89 routes)

### Pages

| Route | Description |
|-------|-------------|
| `GET /` | Dashboard home |
| `GET /vault` | Memory vault |
| `GET /inbox` | Creator inbox |
| `GET /narratives` | Narrative viewer |
| `GET /journals` | Journal viewer |
| `GET /state` | State inspector |
| `GET /boundary` | Boundary events |
| `GET /chat` | Chat interface |
| `GET /profiles` | Profile manager |
| `GET /settings` | Settings page |
| `GET /tools` | Tool registry |
| `GET /notes-list` | Notes list |
| `GET /notes-trash` | Notes trash |
| `GET /notes/{id}` | Note editor |

### Chat API

Send messages, run burst sessions, manage chat history with folders and titles.

### TTS / STT APIs

- **TTS:** openedai-speech integration (Piper CPU + XTTS v2 GPU) — generate speech, list voices
- **STT:** Whisper integration — transcribe audio, check status

### Data Management APIs

- **Vault:** Stats, compact, delete, configure max-active
- **Inbox:** Delete individual messages, clear all
- **Boundary:** Delete events, clear log
- **Journals:** Delete entries, clear
- **Narratives:** Clear, delete sections
- **State:** Delete messages, clear

### Profiles API

View/edit agent config, upload avatars, create new agents, manage per-user settings.

### Connections API

CRUD for LLM provider connections (OpenAI, Ollama, etc.), TTS, and STT services. Assign connections to agents, list available models.

### Notes API

Full CRUD with emoji labels, duplicate, bulk delete, folder organization, trash/restore/permanent-delete, AI-powered text transforms, section reordering.

### Tools API

List registered tools, configure web_search (mode presets, SearXNG URL, Knowledge Gate), configure email accounts.

### Settings API

Get/put global settings, upload/delete chat backgrounds.

## External Service Dependencies

| Service | Purpose | Default URL |
|---------|---------|-------------|
| SearXNG | Web search for `web_search` tool | `http://localhost:3000` |
| openedai-speech | Text-to-speech | `http://localhost:5050` |
| faster-whisper | Speech-to-text | `http://localhost:8060` |

These are configured via `config/connections.json` or Dashboard → Connections. See `tools/` for Docker setup.
