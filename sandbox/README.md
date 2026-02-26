````markdown
# sandbox/

Docker-based sandbox environment for agent experimentation. Gives agents a full Linux container to write code, install packages, and run experiments — without touching the host OS.

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image — Python 3.11 + Node.js 20 + dev tools (vim, git, curl, htop, jq) |
| `docker-compose.yml` | Compose config — resource limits, port mappings, volume mounts, security caps |
| `sandbox.ps1` | PowerShell management script — start, stop, shell, status, reset, logs |

## Quick Start

```powershell
# Start the sandbox
.\sandbox\sandbox.ps1 start

# Open a shell inside the container
.\sandbox\sandbox.ps1 shell

# Stop the sandbox
.\sandbox\sandbox.ps1 stop

# Check status
.\sandbox\sandbox.ps1 status

# Reset (wipe workspace and restart fresh)
.\sandbox\sandbox.ps1 reset
```

## Container Specs

| Resource | Limit |
|----------|-------|
| CPU | 4 cores |
| RAM | 4 GB |
| Base image | `python:3.11-slim-bookworm` |
| User | `orion` (non-root) |
| Capabilities | Minimal (`CHOWN`, `DAC_OVERRIDE`, `FOWNER` only) |

## Port Mappings

| Host Port | Container Port | Purpose |
|-----------|---------------|---------|
| 9090 | 9090 | Primary app (Flask/FastAPI) |
| 9091 | 9091 | Secondary app |
| 8888 | 8888 | Jupyter notebook |
| 3100 | 3000 | Node.js / React dev server |
| 3001 | 3001 | Extra dev server |

## Workspace

The container mounts a persistent workspace from the host:

| Host Path | Container Path |
|-----------|---------------|
| `C:\orion-workspace` (default) | `/workspace` |

Override with the `ORION_WORKSPACE_PATH` environment variable.

The workspace is initialized with subdirectories: `code/`, `experiments/`, `notes/`, `self_modifications/`, `logs/`.

## Pre-installed Software

**Python packages:** requests, pyyaml, flask, fastapi, uvicorn, httpx, beautifulsoup4, markdown, numpy, pytest, black, ruff, ipython

**System tools:** git, curl, wget, vim, nano, htop, jq, tree, zip, build-essential, net-tools

**Node.js:** v20 (via nodesource)

## Security

- Runs as non-root user (`orion`)
- All Linux capabilities dropped except `CHOWN`, `DAC_OVERRIDE`, `FOWNER`
- Resource limits enforced (4 CPU, 4 GB RAM)
- Host filesystem isolated — only the workspace volume is mounted

````
