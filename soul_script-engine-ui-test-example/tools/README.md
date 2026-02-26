# tools/ — External Services & Docker Containers

This folder contains setup files, configs, and documentation for each
**external service** that the agent-runtime tools depend on.

> **Note:** The tool *logic* (Python classes, dispatch, definitions) lives in
> `src/tools/`. This `tools/` folder is only for the external services,
> Docker containers, and helper scripts those tools connect to.

---

## Overview

| Folder | Service | Type | Port | Required By |
|--------|---------|------|------|-------------|
| [`searxng/`](searxng/) | SearXNG meta-search engine | Docker | 3000 | `web_search` tool |
| [`openedai_speech/`](openedai_speech/) | openedai-speech (TTS) | Docker (GPU) | 5050 | Agent voice output |
| [`whisper_stt/`](whisper_stt/) | faster-whisper-server (STT) | Docker | 8060 | Voice transcription |
| [`email_service/`](email_service/) | SMTP email relay | Python (FastAPI) | 8000 | `email` tool (optional) |

---

## Quick Start — All Docker Services

Start all Docker containers at once:

```bash
cd tools/searxng   && docker-compose up -d && cd ../..
cd tools/openedai_speech && docker-compose up -d && cd ../..
cd tools/whisper_stt && docker-compose up -d && cd ../..
```

Or pull all images first:

```bash
docker pull searxng/searxng:latest
docker pull ghcr.io/matatonic/openedai-speech:latest
docker pull fedirz/faster-whisper-server:latest-cpu
```

---

## Built-in Tools (No External Service Needed)

These tools are pure Python and need no Docker container or external service:

| Tool | Description |
|------|-------------|
| `echo` | Simple echo for testing |
| `continuation_update` | Post continuation updates |
| `memory` | Read/write agent memory vault |
| `directives` | Manage runtime directives |

---

## Architecture

```
agent-runtime/
├── src/tools/           # Tool logic (Python classes)
│   └── ...              # Built-in tools
│
├── tools/               # ← YOU ARE HERE — external service files
│   ├── searxng/         # Docker: SearXNG search engine
│   ├── openedai_speech/  # Docker: openedai-speech TTS (Piper CPU + XTTS GPU)
│   ├── whisper_stt/     # Docker: faster-whisper STT
│   └── email_service/   # Python: FastAPI email relay
│
├── config/
│   ├── connections.json # Connection URLs for TTS, STT, LLMs
│   └── settings.json    # Tool config, email accounts, etc.
│
└── web/
    └── app.py           # Dashboard — proxies TTS/STT requests
```

---

## Managing Connections

Docker service URLs are stored in `config/connections.json` and can be
edited from **Dashboard → Connections**.

| Connection ID | Default URL | Service |
|---------------|-------------|---------|
| `edge-tts-local` | `http://localhost:5050` | openedai-speech |
| `whisper-stt-local` | `http://localhost:8060` | faster-whisper |

SearXNG URL is configured per-tool in **Dashboard → Tools → web_search**.

---

## Security

- `email_service/email.env` is excluded from version control (`.gitignore`).
- Never commit SMTP passwords, API keys, or secrets.
- Use app-specific passwords for Gmail (requires 2FA).
