<#
.SYNOPSIS
    Setup and manage the Orion sandbox environment.

.DESCRIPTION
    Creates the workspace folder, builds the Docker image, and starts
    the sandbox container. Orion can execute code freely inside the
    container without affecting the host system.

.PARAMETER Action
    start   - Build image (if needed) and start the sandbox
    stop    - Stop the sandbox container
    restart - Stop and start
    shell   - Open a bash shell inside the running sandbox
    status  - Show container status
    reset   - Stop container, wipe workspace, restart fresh
    logs    - Show container logs

.EXAMPLE
    .\sandbox\sandbox.ps1 start
    .\sandbox\sandbox.ps1 shell
    .\sandbox\sandbox.ps1 stop
#>

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "shell", "status", "reset", "logs", "build")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"

# --- Configuration ---
$WorkspacePath = $env:ORION_WORKSPACE_PATH
if (-not $WorkspacePath) { $WorkspacePath = "C:\orion-workspace" }
$SandboxDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile   = Join-Path $SandboxDir "docker-compose.yml"
$ContainerName = "orion-sandbox"

function Ensure-Workspace {
    if (-not (Test-Path $WorkspacePath)) {
        Write-Host "[sandbox] Creating workspace at $WorkspacePath ..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Path $WorkspacePath -Force | Out-Null

        # Create initial folder structure for Orion
        $folders = @("code", "experiments", "notes", "self_modifications", "logs")
        foreach ($f in $folders) {
            New-Item -ItemType Directory -Path (Join-Path $WorkspacePath $f) -Force | Out-Null
        }

        # Welcome file
        @"
# Orion Workspace

This is your sandboxed workspace. You can freely:
- Write and run code in `code/`
- Run experiments in `experiments/`
- Keep notes in `notes/`
- Modify your own tools in `self_modifications/`
- Check logs in `logs/`

Everything here persists across container restarts.
The host system cannot be affected from inside this container.
"@ | Set-Content (Join-Path $WorkspacePath "README.md") -Encoding UTF8

        Write-Host "[sandbox] Workspace created with folders: $($folders -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "[sandbox] Workspace exists at $WorkspacePath" -ForegroundColor Gray
    }
}

function Start-Sandbox {
    Ensure-Workspace

    Write-Host "[sandbox] Building and starting sandbox ..." -ForegroundColor Cyan
    $env:ORION_WORKSPACE_PATH = $WorkspacePath

    Push-Location $SandboxDir
    try {
        docker compose -f $ComposeFile up -d --build 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Docker compose failed" }
    } finally {
        Pop-Location
    }

    # Wait for container to be healthy
    Start-Sleep -Seconds 2
    $state = docker inspect -f "{{.State.Running}}" $ContainerName 2>$null
    if ($state -eq "true") {
        Write-Host ""
        Write-Host "=== Orion Sandbox Running ===" -ForegroundColor Green
        Write-Host "  Container:  $ContainerName"
        Write-Host "  Workspace:  $WorkspacePath -> /workspace (inside container)"
        Write-Host "  CPU Limit:  4 cores"
        Write-Host "  RAM Limit:  4 GB"
        Write-Host ""
        Write-Host "  Quick commands:" -ForegroundColor Yellow
        Write-Host "    .\sandbox\sandbox.ps1 shell     # Open bash inside sandbox"
        Write-Host "    .\sandbox\sandbox.ps1 stop      # Stop the sandbox"
        Write-Host "    .\sandbox\sandbox.ps1 status    # Check status"
        Write-Host ""
    } else {
        Write-Host "[sandbox] ERROR: Container did not start properly" -ForegroundColor Red
        docker logs $ContainerName 2>&1
    }
}

function Stop-Sandbox {
    Write-Host "[sandbox] Stopping sandbox ..." -ForegroundColor Yellow
    Push-Location $SandboxDir
    try {
        docker compose -f $ComposeFile down 2>&1
    } finally {
        Pop-Location
    }
    Write-Host "[sandbox] Stopped." -ForegroundColor Green
}

function Open-Shell {
    $state = docker inspect -f "{{.State.Running}}" $ContainerName 2>$null
    if ($state -ne "true") {
        Write-Host "[sandbox] Container not running. Starting ..." -ForegroundColor Yellow
        Start-Sandbox
    }
    Write-Host "[sandbox] Opening bash shell (type 'exit' to leave) ..." -ForegroundColor Cyan
    docker exec -it $ContainerName bash
}

function Show-Status {
    $exists = docker ps -a --filter "name=$ContainerName" --format "{{.Status}}" 2>$null
    if ($exists) {
        Write-Host "[sandbox] Container: $exists" -ForegroundColor Cyan
        
        # Show resource usage
        docker stats $ContainerName --no-stream --format "  CPU: {{.CPUPerc}}  MEM: {{.MemUsage}}  NET: {{.NetIO}}" 2>$null
        
        # Show workspace size
        if (Test-Path $WorkspacePath) {
            $size = (Get-ChildItem $WorkspacePath -Recurse -ErrorAction SilentlyContinue | 
                     Measure-Object -Property Length -Sum).Sum
            $sizeMB = [math]::Round($size / 1MB, 1)
            Write-Host "  Workspace: $sizeMB MB ($WorkspacePath)" -ForegroundColor Gray
        }
    } else {
        Write-Host "[sandbox] Container not found. Run: .\sandbox\sandbox.ps1 start" -ForegroundColor Yellow
    }
}

function Reset-Sandbox {
    Write-Host "[sandbox] WARNING: This will delete all workspace contents!" -ForegroundColor Red
    $confirm = Read-Host "  Type 'yes' to confirm"
    if ($confirm -ne "yes") {
        Write-Host "[sandbox] Cancelled." -ForegroundColor Yellow
        return
    }

    Stop-Sandbox
    
    if (Test-Path $WorkspacePath) {
        Write-Host "[sandbox] Wiping workspace ..." -ForegroundColor Yellow
        Remove-Item $WorkspacePath -Recurse -Force
    }
    
    Start-Sandbox
    Write-Host "[sandbox] Fresh sandbox ready." -ForegroundColor Green
}

function Show-Logs {
    docker logs $ContainerName --tail 50 -f 2>&1
}

# --- Main ---
switch ($Action) {
    "start"   { Start-Sandbox }
    "stop"    { Stop-Sandbox }
    "restart" { Stop-Sandbox; Start-Sandbox }
    "shell"   { Open-Shell }
    "status"  { Show-Status }
    "reset"   { Reset-Sandbox }
    "logs"    { Show-Logs }
    "build"   { 
        Push-Location $SandboxDir
        docker compose -f $ComposeFile build --no-cache 2>&1
        Pop-Location
    }
}
