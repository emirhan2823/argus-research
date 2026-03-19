# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$Strategy = "council",
  [string]$RunDir = "runs/year2/paper_main",
  [int]$WaitSec = 4
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $PSBoundParameters.ContainsKey("RunDir") -and $env:ARGUS_RUN_DIR) {
  $RunDir = $env:ARGUS_RUN_DIR
}

if (-not $PSBoundParameters.ContainsKey("WaitSec") -and $env:SOAK_SMOKE_WAIT_SEC) {
  $parsedWaitSec = 0
  if ([int]::TryParse($env:SOAK_SMOKE_WAIT_SEC, [ref]$parsedWaitSec) -and $parsedWaitSec -gt 0) {
    $WaitSec = $parsedWaitSec
  }
}

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
$RunDir = [System.IO.Path]::GetFullPath($RunDir)

$PidFile = if ($env:ARGUS_PID_FILE) { $env:ARGUS_PID_FILE } else { Join-Path $RunDir "daemon.pid" }
if (-not [System.IO.Path]::IsPathRooted($PidFile)) {
  $PidFile = Join-Path $RepoRoot $PidFile
}
$PidFile = [System.IO.Path]::GetFullPath($PidFile)

if (Test-Path $PidFile) {
  Write-Host "[win_soak_smoke] ERROR: pidfile still exists ($PidFile)"
  exit 1
}

Write-Host "[win_soak_smoke] OK"
