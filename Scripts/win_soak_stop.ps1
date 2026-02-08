# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RunDir = "runs/year2/paper_main",
  [int]$GracePeriodSec = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not [System.IO.Path]::IsPathRooted($RunDir)) {
  $RunDir = Join-Path $RepoRoot $RunDir
}
$RunDir = [System.IO.Path]::GetFullPath($RunDir)

$PidFile = Join-Path $RunDir "daemon.pid"
if (-not (Test-Path $PidFile)) {
  Write-Host "[win_soak_stop] pidfile not found ($PidFile)"
  exit 0
}

$pidRaw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue)
$pidValue = 0
if (-not $pidRaw -or -not [int]::TryParse($pidRaw.Trim(), [ref]$pidValue)) {
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "[win_soak_stop] empty/invalid pidfile cleaned"
  exit 0
}

$proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
if ($proc) {
  Write-Host "[win_soak_stop] stopping pid=$pidValue"
  Stop-Process -Id $pidValue -ErrorAction SilentlyContinue

  for ($i = 0; $i -lt ($GracePeriodSec * 2); $i++) {
    Start-Sleep -Milliseconds 500
    if (-not (Get-Process -Id $pidValue -ErrorAction SilentlyContinue)) {
      break
    }
  }

  if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
    Write-Host "[win_soak_stop] forcing kill pid=$pidValue"
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
  }
} else {
  Write-Host "[win_soak_stop] stale pid=$pidValue"
}

Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "[win_soak_stop] pidfile cleaned"
