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

$PidFile = Join-Path $RunDir "daemon.pid"
$HeartbeatFile = Join-Path $RunDir "heartbeat.json"
$MetricsFile = Join-Path $RunDir "metrics.json"
$LogFile = Join-Path $RunDir "daemon.log"
$ErrFile = Join-Path $RunDir "daemon.err.log"

function Show-LogHints {
  if (-not (Test-Path $ErrFile)) {
    Write-Host "Err log: missing ($ErrFile)"
    return
  }
  Write-Host "Err hints (tail):"
  Get-Content -Path $ErrFile -Tail 12
}

function Show-PidState {
  if (-not (Test-Path $PidFile)) {
    Write-Host "PID: not found"
    Show-LogHints
    return
  }
  $pidRaw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue)
  if (-not $pidRaw) {
    Write-Host "PID: invalid pidfile"
    Show-LogHints
    return
  }
  $pidValue = 0
  if (-not [int]::TryParse($pidRaw.Trim(), [ref]$pidValue)) {
    Write-Host "PID: invalid pidfile value '$pidRaw'"
    Show-LogHints
    return
  }
  $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
  if ($proc) {
    Write-Host "PID: $pidValue (running)"
  } else {
    Write-Host "PID: $pidValue (stale)"
    Show-LogHints
  }
}

function Show-Heartbeat {
  if (-not (Test-Path $HeartbeatFile)) {
    Write-Host "Heartbeat: missing ($HeartbeatFile)"
    return
  }
  try {
    $hb = Get-Content -Path $HeartbeatFile -Raw | ConvertFrom-Json
  } catch {
    Write-Host "Heartbeat: unreadable ($($_.Exception.Message))"
    return
  }

  $tsIso = $hb.ts_iso
  if ($tsIso) {
    try {
      $ts = [DateTimeOffset]::Parse($tsIso)
      $ageSec = [Math]::Round(([DateTimeOffset]::UtcNow - $ts.ToUniversalTime()).TotalSeconds, 1)
      Write-Host "Heartbeat: ts=$tsIso age_sec=$ageSec"
    } catch {
      Write-Host "Heartbeat: ts=$tsIso"
    }
  } else {
    Write-Host "Heartbeat: ts_iso missing"
  }

  $counters = $hb.counters
  if ($counters) {
    Write-Host ("Counters: bars_seen={0} decisions_total={1} trades_total={2} rejects_total={3}" -f `
      $counters.bars_seen, $counters.decisions_total, $counters.trades_total, $counters.rejects_total)
  }
  $health = $hb.health
  if ($health) {
    Write-Host ("Health: consecutive_errors={0} last_error={1}" -f $health.consecutive_errors, $health.last_error)
  }
  if ($hb.risk_level) {
    Write-Host ("RiskLevel: {0}" -f $hb.risk_level)
  }
}

function Show-Metrics {
  if (-not (Test-Path $MetricsFile)) {
    Write-Host "Metrics: missing ($MetricsFile)"
    return
  }
  try {
    $m = Get-Content -Path $MetricsFile -Raw | ConvertFrom-Json
  } catch {
    Write-Host "Metrics: unreadable ($($_.Exception.Message))"
    return
  }
  Write-Host ("Metrics: bars_seen={0} trades_total={1} rejects_total={2} errors_total={3}" -f `
    $m.bars_seen, $m.trades_total, $m.rejects_total, $m.errors_total)
  if ($m.last_error) {
    Write-Host ("Metrics last_error: {0}" -f $m.last_error)
  }
  if ($m.strategy_id_breakdown) {
    Write-Host ("Metrics strategy_id_breakdown: {0}" -f ($m.strategy_id_breakdown | ConvertTo-Json -Compress))
  }
}

function Show-Logs {
  if (Test-Path $LogFile) {
    Write-Host "Log tail ($LogFile):"
    Get-Content -Path $LogFile -Tail 30
  } else {
    Write-Host "Log: missing ($LogFile)"
  }
  if (Test-Path $ErrFile) {
    Write-Host "Err tail ($ErrFile):"
    Get-Content -Path $ErrFile -Tail 20
  }
}

Write-Host "=== ARGUS PAPER SOAK STATUS (Windows) ==="
Write-Host "Run dir: $RunDir"
Show-PidState
Show-Heartbeat
Show-Metrics
Show-Logs
