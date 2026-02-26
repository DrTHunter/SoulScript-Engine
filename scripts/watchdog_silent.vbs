' ── Silent Watchdog Launcher ──────────────────────────────────────────
' Launches watchdog.ps1 with NO visible window at all.
' Use this as the Task Scheduler action instead of powershell.exe directly.
' ─────────────────────────────────────────────────────────────────────
Set objShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File """ & scriptDir & "\watchdog.ps1"""", 0, False
