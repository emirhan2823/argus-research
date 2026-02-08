# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$Strategy = "council",
  [string]$RunDir = "runs/year2/paper_main",
  [int]$WaitSec = 4
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$StartScript = Join-Path $PSScriptRoot "win_soak_start.ps1"
$StatusScript = Join-Path $PSScriptRoot "win_soak_status.ps1"
$StopScript = Join-Path $PSScriptRoot "win_soak_stop.ps1"

& $StartScript -Strategy $Strategy -RunDir $RunDir
Start-Sleep -Seconds $WaitSec
& $StatusScript -RunDir $RunDir
& $StopScript -RunDir $RunDir

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not [System.IO.Path]::IsPathRooted($RunDir)) {
  $RunDir = Join-Path $RepoRoot $RunDir
}
$PidFile = Join-Path ([System.IO.Path]::GetFullPath($RunDir)) "daemon.pid"

if (Test-Path $PidFile) {
  Write-Host "[win_soak_smoke] ERROR: pidfile still exists ($PidFile)"
  exit 1
}

Write-Host "[win_soak_smoke] OK"
