# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RunDir = "runs/year2/paper_main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not [System.IO.Path]::IsPathRooted($RunDir)) {
  $RunDir = Join-Path $RepoRoot $RunDir
}
$RunDir = [System.IO.Path]::GetFullPath($RunDir)

$PidFile = Join-Path $RunDir "dashboard.pid"
if (-not (Test-Path $PidFile)) {
  Write-Host "[win_dashboard_stop] pidfile not found ($PidFile)"
  exit 0
}

$pidRaw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue)
$pidValue = 0
if (-not $pidRaw -or -not [int]::TryParse($pidRaw.Trim(), [ref]$pidValue)) {
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "[win_dashboard_stop] empty/invalid pidfile cleaned"
  exit 0
}

if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
  Write-Host "[win_dashboard_stop] stopping pid=$pidValue"
  Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
} else {
  Write-Host "[win_dashboard_stop] stale pid=$pidValue"
}

Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "[win_dashboard_stop] pidfile cleaned"
