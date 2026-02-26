# ── Orion Forge Watchdog ─────────────────────────────────────────────
# Runs every 5 minutes via Task Scheduler.
# Checks that all critical services are alive and restarts any that died.
# ─────────────────────────────────────────────────────────────────────

$PROJECT_DIR = (Split-Path -Parent $PSScriptRoot)  # auto-resolve from scripts\
$PYTHON_EXE  = "C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe"
$OPEN_WEBUI  = "C:\Users\user\AppData\Local\Programs\Python\Python311\Scripts\open-webui.exe"
$LOG_FILE    = "$PROJECT_DIR\logs\watchdog.log"

New-Item -ItemType Directory -Path "$PROJECT_DIR\logs" -Force | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  [watchdog]  $msg" | Tee-Object -FilePath $LOG_FILE -Append
}

# ── Orion Forge Dashboard (port 8585) ──
if (-not (Get-NetTCPConnection -LocalPort 8585 -ErrorAction SilentlyContinue)) {
    Log "Dashboard DOWN - restarting on port 8585"
    Start-Process -FilePath $PYTHON_EXE `
        -ArgumentList "-m","uvicorn","web.app:app","--host","0.0.0.0","--port","8585" `
        -WorkingDirectory $PROJECT_DIR `
        -WindowStyle Hidden
} else {
    Log "Dashboard OK (8585)"
}

# ── Open WebUI (port 8080) ──
if (-not (Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue)) {
    Log "Open WebUI DOWN - restarting on port 8080"
    Start-Process -FilePath $OPEN_WEBUI `
        -ArgumentList "serve","--port","8080" `
        -WindowStyle Hidden
} else {
    Log "Open WebUI OK (8080)"
}

# ── Ollama ──
if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Log "Ollama DOWN - restarting"
    Start-Process "C:\Users\user\AppData\Local\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
} else {
    Log "Ollama OK"
}

# ── Email Service (port 8000) ──
if (-not (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue)) {
    Log "Email Service DOWN - restarting on port 8000"
    Start-Process -FilePath $PYTHON_EXE `
        -ArgumentList "main.py" `
        -WorkingDirectory "C:\Users\user\OneDrive\Desktop\Library\Orion Forge\tools\Email Tool\Runtime Folder" `
        -WindowStyle Hidden
} else {
    Log "Email Service OK (8000)"
}

# ── Cloudflared tunnel (runs as user process, not Windows service) ──
if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
    Log "Cloudflared DOWN - restarting as user process"
    Start-Process -FilePath "C:\Program Files (x86)\cloudflared\cloudflared.exe" `
        -ArgumentList "tunnel","run" `
        -WindowStyle Hidden
} else {
    Log "Cloudflared OK"
}
