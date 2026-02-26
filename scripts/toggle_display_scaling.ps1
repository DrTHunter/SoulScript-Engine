# ── Toggle Display Scaling (Left Monitor) ──────────────────────────
# Toggles the left/primary monitor between 100% and 150% scaling.
# Creates a brief desktop flicker as Explorer restarts to apply.
# ───────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

# Left monitor registry key (HKC 27N1 via NVIDIA RTX 3060)
$regPath = "HKCU:\Control Panel\Desktop\PerMonitorSettings"
$monitorKey = "HKC27130000000000001_1A_07E5_79_10DE_2487_00000001_00000000_1204^E8645ADC2DC202698A38DD42DACF5BA5"
$fullPath = "$regPath\$monitorKey"

# DpiValue: 0 = 100%, 2 = 150%
$current = (Get-ItemProperty -Path $fullPath -Name DpiValue).DpiValue

if ($current -eq 0) {
    # Switch to 150%
    Set-ItemProperty -Path $fullPath -Name DpiValue -Value 2
    $newScale = "150%"
} else {
    # Switch to 100%
    Set-ItemProperty -Path $fullPath -Name DpiValue -Value 0
    $newScale = "100%"
}

# Apply by restarting Explorer (causes a brief ~2s desktop flicker)
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Start-Process explorer.exe

# Toast notification (Windows 10/11)
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show(
    "Display scaling set to $newScale",
    "Orion Forge - Display Toggle",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null
