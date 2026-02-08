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
$LogFile = Join-Path $RunDir "dashboard.log"
$ErrFile = Join-Path $RunDir "dashboard.err.log"

Write-Host "=== ARGUS DASHBOARD STATUS (Windows) ==="
Write-Host "Run dir: $RunDir"

if (-not (Test-Path $PidFile)) {
  Write-Host "PID: not found"
} else {
  $pidRaw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue)
  $pidValue = 0
  if ($pidRaw -and [int]::TryParse($pidRaw.Trim(), [ref]$pidValue)) {
    if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
      Write-Host "PID: $pidValue (running)"
    } else {
      Write-Host "PID: $pidValue (stale)"
    }
  } else {
    Write-Host "PID: invalid pidfile"
  }
}

if (Test-Path $LogFile) {
  Write-Host "Log tail ($LogFile):"
  Get-Content -Path $LogFile -Tail 25
} else {
  Write-Host "Log: missing ($LogFile)"
}

if (Test-Path $ErrFile) {
  Write-Host "Err tail ($ErrFile):"
  Get-Content -Path $ErrFile -Tail 25
}
