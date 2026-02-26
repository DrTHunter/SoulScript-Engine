# Agent Runtime — Session Export (Feb 15, 2026)

> **Purpose**: Upload this file to a Claude.ai Project as "Project Knowledge" so Claude has full context of the agent-runtime codebase, architecture, and this session's work.

---

## 1. Project Overview

**agent-runtime** is a Python-based AI agent orchestration framework located at `C:\Users\user\agent-runtime`. It runs autonomous agents (primarily "Orion") in a loop, routing stimuli through LLM providers, tools, memory, directives, and governance policies.

### Key Directories

| Path | Purpose |
|------|---------|
| `src/` | Core runtime: loop, router, LLM clients, tools, memory, governance |
| `src/llm_client/` | LLM provider abstraction (OpenAI, Ollama, Anthropic) |
| `src/tools/` | Tool implementations (echo, memory, email, web_search, computer_use, etc.) |
| `src/memory/` | Embedding-based memory (vault, scopes) |
| `src/directives/` | Agent directive system (injector, parser, store) |
| `src/governance/` | Active directives, change log |
| `profiles/` | Agent YAML configs (provider, model, tools, memory settings) |
| `prompts/` | System prompt markdown files per agent |
| `directives/` | Directive markdown files per agent |
| `notes/` | Operator notes per agent |
| `data/` | Runtime data: journals, narratives, chats, memory vaults, shared inboxes |
| `web/` | FastAPI web dashboard (port 8585) |
| `sandbox/` | Docker sandbox for Computer Use (Dockerfile, compose, management script) |
| `tools/` | External service tools (edge_tts, email_service, searxng, whisper_stt) |
| `config/` | Settings, connections, pricing config |
| `scripts/` | Maintenance scripts (backup, vault maintenance) |
| `tests/` | Test suite |

---

## 2. Architecture

### LLM Client Abstraction

```
src/llm_client/base.py    → LLMClient (ABC), LLMResponse dataclass
src/llm_client/factory.py → create_client(profile) dispatches to provider
src/llm_client/openai_compat.py → OpenAICompatClient (OpenAI API)
src/llm_client/ollama.py  → OllamaClient (local Ollama)
src/llm_client/anthropic_client.py → AnthropicClient (Anthropic Messages API) [NEW]
```

**LLMResponse** (canonical response):
```python
@dataclass
class LLMResponse:
    content: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    # Each tool_call: {"call_id": str, "tool": str, "arguments": dict}
    model: str = ""
    usage: Optional[Dict[str, int]] = None
    raw: Dict[str, Any] = field(default_factory=dict)
```

**Factory registration** (`src/llm_client/factory.py`):
```python
_PROVIDERS = {
    "openai": OpenAICompatClient,
    "ollama": OllamaClient,
    "anthropic": AnthropicClient,
}
```

### Agent Loop

The main loop (`src/loop.py`) loads a profile YAML, creates an LLM client via the factory, collects tool definitions from the registry, injects directives and memory, then runs a stimulus→response→tool-dispatch cycle.

Run an agent:
```
python -m src.loop --profile orion
python -m src.loop --profile orion-claude
python -m src.loop --profile orion-computer
```

### Tool Registry

`src/tools/registry.py` maintains a master catalog of all tools:
```python
_ALL_TOOLS = {
    "echo": EchoTool(),
    "task_inbox": TaskInboxTool(),
    "continuation_update": ContinuationUpdateTool(),
    "memory": MemoryTool(),
    "directives": DirectivesTool(),
    "runtime_info": RuntimeInfoTool(),
    "creator_inbox": CreatorInboxTool(),
    "web_search": WebSearchTool(),
    "email": EmailTool(),
    "computer_use": ComputerUseTool(),
}
```

Each tool class exposes `definition() -> dict` (JSON schema) and `execute(arguments) -> str`.

The `ToolRegistry` class enforces profile allowlists — only tools listed in `allowed_tools` in the profile YAML are available to each agent. Denied tool calls generate a boundary event and return a denial payload.

---

## 3. Agent Profiles

### orion.yaml (Primary — GPT-5.2)
```yaml
name: orion
provider: openai
model: gpt-5.2
base_url: https://api.openai.com/v1
temperature: 0.7
system_prompt: orion.system.md
window_size: 50
allowed_tools:
- continuation_update
- directives
- echo
- email
- memory
- task_inbox
- creator_inbox
- web_search
policy:
  max_iterations: 25
  stasis_mode: false
  tool_failure_mode: continue
memory:
  enabled: true
  scopes: [shared, orion]
  max_items: 20
  similarity_threshold: 0.85
directives:
  enabled: true
  scopes: [shared, orion]
  max_sections: 5
edge_voice: fable
voice_id: 8vf2Pg7VZD0Piv8GA8v9
```

### orion-claude.yaml (Claude Sonnet — no Computer Use)
```yaml
name: orion-claude
provider: anthropic
model: claude-sonnet-4-20250514
base_url: https://api.anthropic.com
temperature: 0.7
max_tokens: 4096
system_prompt: orion.system.md
# Same tools, memory, directives, policy as orion.yaml
# No computer_use capability
```

### orion-computer.yaml (Claude Sonnet + Computer Use)
```yaml
name: orion-computer
provider: anthropic
model: claude-sonnet-4-20250514
base_url: https://api.anthropic.com
temperature: 0.5
max_tokens: 4096
computer_use: true  # ← enables Computer Use beta header & tools
system_prompt: orion.system.md
allowed_tools:
- continuation_update
- directives
- echo
- email
- memory
- task_inbox
- creator_inbox
- web_search
- computer_use  # ← extra tool
```

---

## 4. Anthropic Client (NEW — `src/llm_client/anthropic_client.py`)

Native Anthropic Messages API client. Key features:

- **System message separation**: Extracts system message from conversation and passes as top-level `system` parameter
- **Message format conversion**: Converts internal format → Anthropic format:
  - Tool results sent as `role: "user"` with `tool_result` content blocks
  - Assistant tool calls use `tool_use` content blocks
- **Computer Use support**: When `computer_use: true` in profile:
  - Adds `anthropic-beta: computer-use-2024-10-22` header
  - Injects Computer Use tool definitions (computer_20241022, bash_20241022, str_replace_editor_20241022)
- **Auth**: Uses `ANTHROPIC_API_KEY` environment variable (set as persistent user env var)
- **Tested**: Live API call confirmed working with Claude Sonnet

### Full Source

```python
"""Anthropic Messages API client."""

import json, os, uuid
from typing import Any, Dict, List, Optional
import requests
from src.llm_client.base import LLMClient, LLMResponse

class AnthropicClient(LLMClient):
    KNOWN_MODELS = {
        "claude-sonnet-4-20250514": 200_000,
        "claude-opus-4-20250514": 200_000,
        "claude-3-5-sonnet-20241022": 200_000,
        "claude-3-5-haiku-20241022": 200_000,
        "claude-3-opus-20240229": 200_000,
    }

    def __init__(self, profile: dict):
        self.model = profile["model"]
        self.base_url = profile.get("base_url", "https://api.anthropic.com").rstrip("/")
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.temperature = profile.get("temperature", 0.7)
        self.max_tokens = profile.get("max_tokens", 4096)
        self.computer_use = profile.get("computer_use", False)
        if not self.api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")

    def chat(self, messages, tools=None) -> LLMResponse:
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.computer_use:
            headers["anthropic-beta"] = "computer-use-2024-10-22"

        system_text, conv_messages = self._extract_system(messages)
        body = {
            "model": self.model,
            "messages": self._convert_messages(conv_messages),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if system_text:
            body["system"] = system_text

        api_tools = self._build_tools(tools)
        if api_tools:
            body["tools"] = api_tools

        resp = requests.post(f"{self.base_url}/v1/messages", headers=headers, json=body, timeout=180)
        resp.raise_for_status()
        return self._parse_response(resp.json())

    # Tool schema: converts internal defs + adds Computer Use built-in tools
    # Response parsing: extracts text blocks + tool_use blocks → LLMResponse
    # Message conversion: handles tool_result as user content, tool_use as assistant content
```

---

## 5. Computer Use Tool (NEW — `src/tools/computer_use.py`)

Executes Anthropic Computer Use actions in a Docker sandbox. Three action types:

| Tool Type | Actions | Implementation |
|-----------|---------|----------------|
| `computer` | screenshot, click, double_click, move, type, key, scroll | xdotool/scrot in container |
| `bash` | Execute shell commands | `docker exec` into container |
| `str_replace_editor` | view, create, str_replace, insert files | Bash/Python in container |

### Safety Model
- **Default**: All actions run in Docker container (`COMPUTER_USE_SANDBOX=true`)
- **Local fallback**: Set `COMPUTER_USE_SANDBOX=false` for pyautogui/PIL (dangerous)
- **Audit log**: Every action logged to `data/shared/computer_use_log.jsonl`

### Configuration Environment Variables
```
COMPUTER_USE_SANDBOX=true          # sandbox mode (default)
COMPUTER_USE_IMAGE=orion-sandbox   # Docker image name
COMPUTER_USE_CONTAINER=orion-sandbox  # container name
ORION_WORKSPACE_PATH=C:\orion-workspace  # host workspace mount
```

### Key Classes
- `_SandboxExecutor` — Docker-based execution (ensure_running, exec_bash, screenshot, mouse/keyboard, scroll)
- `_LocalExecutor` — Host-based execution via pyautogui/PIL (for dev/testing only)
- `ComputerUseTool` — Registry-compatible wrapper with `definition()` and `execute()`

---

## 6. Docker Sandbox Infrastructure

### Dockerfile (`sandbox/Dockerfile`)
```dockerfile
FROM python:3.11-slim-bookworm
# System: build-essential, git, curl, wget, vim, nano, net-tools, htop, etc.
# Python: requests, pyyaml, flask, fastapi, uvicorn, httpx, numpy, pytest, black, ruff, ipython
# Node.js 20.x
# Non-root user: orion
# VOLUME /workspace
# CMD: tail -f /dev/null (keep alive)
```
**Image size**: ~1.35 GB

### docker-compose.yml (`sandbox/docker-compose.yml`)
```yaml
services:
  orion-sandbox:
    build: { context: ., dockerfile: Dockerfile }
    container_name: orion-sandbox
    hostname: orion-sandbox
    volumes:
      - ${ORION_WORKSPACE_PATH:-C:/orion-workspace}:/workspace
    ports:
      - "9090:9090"   # Primary app
      - "9091:9091"   # Secondary app
      - "8888:8888"   # Jupyter notebook
      - "3100:3000"   # Node.js (host 3100 → container 3000, port 3000 was taken)
      - "3001:3001"   # Extra dev server
    deploy:
      resources:
        limits: { cpus: "4.0", memory: 4G }
        reservations: { cpus: "1.0", memory: 512M }
    cap_drop: [ALL]
    cap_add: [CHOWN, DAC_OVERRIDE, FOWNER, SETGID, SETUID]
    security_opt: [no-new-privileges:true]
    restart: unless-stopped
    tty: true
    stdin_open: true
```

### Management Script (`sandbox/sandbox.ps1`)
```powershell
.\sandbox\sandbox.ps1 start    # Build & start
.\sandbox\sandbox.ps1 stop     # Stop container
.\sandbox\sandbox.ps1 restart  # Restart
.\sandbox\sandbox.ps1 shell    # Bash shell inside container
.\sandbox\sandbox.ps1 status   # Show status, CPU, memory, workspace size
.\sandbox\sandbox.ps1 reset    # Wipe workspace & restart
.\sandbox\sandbox.ps1 logs     # View container logs
.\sandbox\sandbox.ps1 build    # Rebuild image
```

### Host Workspace
- **Path**: `C:\orion-workspace`
- **Folders**: `code/`, `experiments/`, `notes/`, `self_modifications/`, `logs/`
- **Mounts to**: `/workspace` inside the container
- **Persists** across container restarts

---

## 7. Environment Variables

| Variable | Value | Storage |
|----------|-------|---------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-qBuJ...gOd5bQAA` | Persistent user env var |
| `OPENAI_API_KEY` | (must be set manually) | Was hardcoded, now reads from env |
| `COMPUTER_USE_SANDBOX` | `true` (default) | Not explicitly set |

**Important**: The OpenAI API key was previously hardcoded in `src/llm_client/openai_compat.py` and was removed for security. It must now be set as an environment variable to use the `openai` provider.

---

## 8. External Services

| Service | Port | Purpose |
|---------|------|---------|
| Web Dashboard | 8585 | FastAPI/Uvicorn chat UI (has persistent startup issues) |
| Edge-TTS | 5050 | Text-to-speech (OpenAI-compatible API) |
| Whisper STT | 8060 | Speech-to-text transcription |
| Orion Sandbox | 9090, 9091, 8888, 3100, 3001 | Docker sandbox ports |

---

## 9. Dependencies (`requirements.txt`)

```
requests>=2.28.0
pyyaml>=6.0
fastapi>=0.100.0
uvicorn>=0.20.0
jinja2>=3.1.0
markdown>=3.4.0
python-multipart>=0.0.5
beautifulsoup4>=4.12.0
trafilatura>=1.6.0
anthropic>=0.39.0
pyautogui>=0.9.54
Pillow>=10.0.0
```

---

## 10. Known Issues

1. **Web app startup**: `python -m web.app` consistently exits with code 1. The module loads fine (`from web.app import app` succeeds) but running as `__main__` fails. `python -m uvicorn web.app:app` also exits 1. The server does serve requests while running (some attempts got 200 responses), suggesting a background process or timing issue. Not yet root-caused.

2. **Port 3000 conflict**: Something on the host already uses port 3000, so the sandbox maps host:3100 → container:3000.

---

## 11. How to Continue This Work

### Running Orion on different providers:
```bash
python -m src.loop --profile orion           # GPT-5.2
python -m src.loop --profile orion-claude     # Claude Sonnet (no Computer Use)
python -m src.loop --profile orion-computer   # Claude Sonnet + Computer Use
```

### Managing the sandbox:
```powershell
.\sandbox\sandbox.ps1 start   # Start Docker sandbox
.\sandbox\sandbox.ps1 shell   # Open bash in sandbox
.\sandbox\sandbox.ps1 status  # Check status
```

### Adding a new LLM provider:
1. Create `src/llm_client/new_provider.py` implementing `LLMClient`
2. Import & register in `src/llm_client/factory.py`
3. Create a profile YAML with `provider: new_provider`

### Adding a new tool:
1. Create `src/tools/my_tool.py` with `definition()` and `execute()`
2. Import & register in `src/tools/registry.py`
3. Add tool name to profile's `allowed_tools` list

---

## 12. File Tree (Key Files)

```
agent-runtime/
├── src/
│   ├── llm_client/
│   │   ├── base.py              # LLMClient ABC, LLMResponse
│   │   ├── factory.py           # Provider factory (openai, ollama, anthropic)
│   │   ├── openai_compat.py     # OpenAI API client
│   │   ├── ollama.py            # Ollama client
│   │   └── anthropic_client.py  # [NEW] Anthropic Messages API client
│   ├── tools/
│   │   ├── registry.py          # Tool catalog + allowlist dispatch
│   │   ├── computer_use.py      # [NEW] Computer Use tool
│   │   ├── echo.py, memory_tool.py, email_tool.py, ...
│   ├── loop.py                  # Main agent loop
│   ├── router.py                # Stimulus routing
│   ├── run_burst.py             # Single burst execution
│   └── runtime_policy.py        # Policy enforcement
├── profiles/
│   ├── orion.yaml               # Primary agent (GPT-5.2)
│   ├── orion-claude.yaml        # [NEW] Claude Sonnet
│   └── orion-computer.yaml      # [NEW] Claude + Computer Use
├── sandbox/
│   ├── Dockerfile               # [NEW] Python 3.11 + Node 20 sandbox
│   ├── docker-compose.yml       # [NEW] Container config with ports
│   └── sandbox.ps1              # [NEW] PowerShell management script
├── web/
│   ├── app.py                   # FastAPI dashboard
│   ├── templates/               # Jinja2 HTML templates
│   └── static/                  # CSS/JS assets
├── data/
│   ├── shared/                  # Shared agent data (inboxes, logs)
│   ├── orion/                   # Orion's journal, narrative, state
│   └── memory/                  # Vault (embeddings)
├── config/
│   ├── connections.json         # Service connection config
│   ├── pricing.yaml             # Token pricing
│   └── settings.json            # Runtime settings
└── requirements.txt             # Python dependencies
```

---

*Generated: February 15, 2026 — VS Code Copilot session export*
