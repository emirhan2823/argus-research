# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RootPath = "E:\argus",
  [string]$RepoPath = "",
  [ValidateSet("crypto", "stock", "defi")]
  [string]$AssetClass = "crypto",
  [int]$TailLines = 25
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
  param([string]$Root, [string]$Repo)
  if ($Repo -and $Repo.Trim().Length -gt 0) {
    return [System.IO.Path]::GetFullPath($Repo)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $Root "argus-terminal"))
}

try {
  $RootPath = [System.IO.Path]::GetFullPath($RootPath)
  $RepoPath = Resolve-RepoPath -Root $RootPath -Repo $RepoPath
  $runDir = Join-Path $RootPath "runs\year2\paper_main_$AssetClass"

  $pidFile = Join-Path $runDir "daemon.pid"
  $heartbeatFile = Join-Path $runDir "heartbeat.json"
  $metricsFile = Join-Path $runDir "metrics.json"
  $logFile = Join-Path $runDir "daemon.log"

  Write-Host "=== ARGUS WINDOWS SOAK STATUS ==="
  Write-Host "AssetClass : $AssetClass"
  Write-Host "RunDir     : $runDir"

  $isRunning = $false
  if (Test-Path $pidFile) {
    $pidRaw = (Get-Content -Path $pidFile -Raw -ErrorAction SilentlyContinue)
    $pidValue = 0
    if ($pidRaw -and [int]::TryParse($pidRaw.Trim(), [ref]$pidValue)) {
      $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
      if ($proc) {
        $isRunning = $true
        Write-Host "PID        : $pidValue (running)"
      } else {
        Write-Host "PID        : $pidValue (stale)"
      }
    } else {
      Write-Host "PID        : invalid pidfile"
    }
  } else {
    Write-Host "PID        : not found"
  }

  if (Test-Path $heartbeatFile) {
    $hb = Get-Content -Path $heartbeatFile -Raw | ConvertFrom-Json
    $tsIso = [string]$hb.ts_iso
    if ($tsIso) {
      try {
        $ts = [DateTimeOffset]::Parse($tsIso)
        $ageSec = [Math]::Round(([DateTimeOffset]::UtcNow - $ts.ToUniversalTime()).TotalSeconds, 1)
        Write-Host "Heartbeat  : ts=$tsIso age_sec=$ageSec"
      } catch {
        Write-Host "Heartbeat  : ts=$tsIso"
      }
    } else {
      Write-Host "Heartbeat  : ts_iso missing"
    }
    if ($hb.counters) {
      Write-Host ("Counters   : bars={0} decisions={1} trades={2} rejects={3}" -f `
        $hb.counters.bars_seen, $hb.counters.decisions_total, $hb.counters.trades_total, $hb.counters.rejects_total)
    }
    if ($hb.risk_level) {
      Write-Host "RiskLevel  : $($hb.risk_level)"
    }
  } else {
    Write-Host "Heartbeat  : missing ($heartbeatFile)"
  }

  if (Test-Path $metricsFile) {
    $m = Get-Content -Path $metricsFile -Raw | ConvertFrom-Json
    Write-Host ("Metrics    : mode={0} asset={1} venue={2} errors={3}" -f `
      $m.mode, $m.asset_class, $m.venue_id, $m.errors_total)
  } else {
    Write-Host "Metrics    : missing ($metricsFile)"
  }

  if (Test-Path $logFile) {
    Write-Host "Log tail   : $logFile"
    Get-Content -Path $logFile -Tail $TailLines
  } else {
    Write-Host "Log tail   : missing ($logFile)"
  }

  if ($isRunning) {
    Write-Host "[windows_soak_status] PASS"
    exit 0
  }
  Write-Host "[windows_soak_status] WARN: daemon running degil"
  exit 1
} catch {
  Write-Host "[windows_soak_status] FAILED: $($_.Exception.Message)"
  exit 1
}

