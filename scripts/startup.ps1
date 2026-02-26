# ── Orion Forge Startup Script ──────────────────────────────────────
# Waits for Docker to be ready, then launches:
#   1. Open WebUI  (port 8080)
#   2. Orion Forge Dashboard  (port 8585)
#
# Designed to run via Task Scheduler at user logon.
# Docker containers auto-start via restart: unless-stopped policy.
# ────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "SilentlyContinue"

$PROJECT_DIR    = (Split-Path -Parent $PSScriptRoot)  # auto-resolve from scripts\
$PYTHON_EXE     = "C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe"
$OPEN_WEBUI_EXE = "C:\Users\user\AppData\Local\Programs\Python\Python311\Scripts\open-webui.exe"
$LOG_FILE       = "$PROJECT_DIR\logs\startup.log"
$DASH_HOST      = "0.0.0.0"
$DASH_PORT      = 8585
$WEBUI_PORT     = 8080
$MAX_DOCKER_WAIT = 120  # seconds to wait for Docker

# Ensure log directory exists
New-Item -ItemType Directory -Path "$PROJECT_DIR\logs" -Force | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LOG_FILE -Append
}

Log "═══ Orion Forge startup initiated ═══"

# ── Wait for Docker Engine ──
Log "Waiting for Docker Engine..."
$waited = 0
while ($waited -lt $MAX_DOCKER_WAIT) {
    $info = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Log "Docker Engine ready after ${waited}s"
        break
    }
    Start-Sleep -Seconds 3
    $waited += 3
}

if ($waited -ge $MAX_DOCKER_WAIT) {
    Log "WARNING: Docker not ready after ${MAX_DOCKER_WAIT}s - containers may not be available"
}

# ── Verify containers are running ──
Start-Sleep -Seconds 5  # give containers a moment to start
$containers = docker ps --format "{{.Names}}" 2>&1
$count = ($containers | Measure-Object -Line).Lines
Log "Docker containers running: $count"

# ── Launch Open WebUI (background) ──
$webuiRunning = Get-NetTCPConnection -LocalPort $WEBUI_PORT -ErrorAction SilentlyContinue
if ($webuiRunning) {
    Log "Open WebUI already running on port $WEBUI_PORT - skipping"
} else {
    Log "Starting Open WebUI on port $WEBUI_PORT..."
    Start-Process -FilePath $OPEN_WEBUI_EXE `
        -ArgumentList "serve", "--port", $WEBUI_PORT `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$PROJECT_DIR\logs\openwebui_stdout.log" `
        -RedirectStandardError "$PROJECT_DIR\logs\openwebui_stderr.log"
    # Wait a moment and verify
    Start-Sleep -Seconds 8
    $webuiCheck = Get-NetTCPConnection -LocalPort $WEBUI_PORT -ErrorAction SilentlyContinue
    if ($webuiCheck) {
        Log "Open WebUI started successfully on port $WEBUI_PORT"
    } else {
        Log "WARNING: Open WebUI may still be starting up on port $WEBUI_PORT"
    }
}

# -- Launch Orion Forge Dashboard (foreground - keeps script alive) --
$dashRunning = Get-NetTCPConnection -LocalPort $DASH_PORT -ErrorAction SilentlyContinue
if ($dashRunning) {
    Log "Dashboard already running on port $DASH_PORT - keeping script alive"
    # Keep the script alive so Task Scheduler doesn't kill the child processes
    while ($true) { Start-Sleep -Seconds 60 }
} else {
    Log "Starting Orion Forge dashboard on port $DASH_PORT..."
    Set-Location $PROJECT_DIR
    # Start uvicorn - this blocks (keeps the script alive)
    & $PYTHON_EXE -m uvicorn web.app:app --host $DASH_HOST --port $DASH_PORT 2>&1 |
        ForEach-Object { Log $_ }
}
