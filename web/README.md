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
| `app.py` | FastAPI application — all routes, helpers, and API endpoints (36 handlers, ~1038 lines) |
| `static/style.css` | Stylesheet for the dashboard |
| `templates/` | Jinja2 HTML templates (10 pages) |

## Templates

| Template | Page |
|----------|------|
| `base.html` | Shared layout (nav, sidebar, footer) |
| `chat.html` | Real-time chat with agents |
| `vault.html` | Memory vault browser with stats, compaction, and management |
| `profiles.html` | Agent profile viewer/editor, avatar upload, create new agents |
| `settings.html` | Timezone, display preferences, chat background |
| `tools.html` | Tool registry with detail panels and config |
| `knowledge.html` | Knowledge notes browser |
| `knowledge_edit.html` | Knowledge note editor |
| `about.html` | About page |

## API Endpoints (36 routes)

### Pages

| Route | Description |
|-------|-------------|
| `GET /` | Dashboard home |
| `GET /chat` | Chat interface |
| `GET /profiles` | Profile manager |
| `GET /vault` | Memory vault |
| `GET /knowledge` | Knowledge notes |
| `GET /knowledge/{note_id}/edit` | Knowledge note editor |
| `GET /settings` | Settings page |
| `GET /tools` | Tool registry |
| `GET /about` | About page |

### Chat API

| Route | Description |
|-------|-------------|
| `POST /api/chat/send` | Send message to agent |
| `GET /api/chat/history` | List all chats |
| `POST /api/chat/new` | Create new chat |
| `GET /api/chat/{chat_id}` | Get chat by ID |
| `DELETE /api/chat/{chat_id}` | Delete chat |
| `PUT /api/chat/{chat_id}` | Update chat |
| `POST /api/chat/{chat_id}/title` | Update chat title |

### Profiles API

| Route | Description |
|-------|-------------|
| `GET /api/profiles/{name}` | Get agent profile |
| `PUT /api/profiles/{name}` | Update agent profile |
| `POST /api/profiles` | Create new agent |
| `DELETE /api/profiles/{name}` | Delete agent |
| `PUT /api/profiles/{name}/knowledge` | Update agent knowledge attachments |

### Vault API

| Route | Description |
|-------|-------------|
| `POST /api/vault/add` | Add memory to vault |
| `GET /api/vault/stats` | Vault statistics |
| `POST /api/vault/delete` | Delete memory |
| `GET /api/vault/compact` | Compact vault |

### Knowledge API

| Route | Description |
|-------|-------------|
| `POST /api/knowledge` | Create knowledge note |
| `PUT /api/knowledge/{note_id}` | Update knowledge note |
| `DELETE /api/knowledge/{note_id}` | Delete knowledge note |
| `GET /api/knowledge/{note_id}` | Get knowledge note |

### Connections API

| Route | Description |
|-------|-------------|
| `GET /api/connections` | List connections |
| `POST /api/connections` | Create connection |
| `PUT /api/connections/{conn_id}` | Update connection |
| `DELETE /api/connections/{conn_id}` | Delete connection |
| `GET /api/connections/{conn_id}/models` | List available models |

### Other

| Route | Description |
|-------|-------------|
| `POST /api/about` | Update about content |
| `GET /api/health` | Health check |

## Startup Behavior

On startup, the app rebuilds the NotesFAISS index and initializes a lazy `FAISSMemory` singleton for vault-backed semantic search.

## External Service Dependencies

| Service | Purpose | Default URL |
|---------|---------|-------------|
| SearXNG | Web search for `web_search` tool | `http://localhost:3000` |
| openedai-speech | Text-to-speech | `http://localhost:5050` |
| faster-whisper | Speech-to-text | `http://localhost:8060` |

These are configured via `config/connections.json` or Dashboard → Connections. See `tools/` for Docker setup.
