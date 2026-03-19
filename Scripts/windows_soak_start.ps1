# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RootPath = "E:\argus",
  [string]$RepoPath = "",
  [ValidateSet("crypto", "stock", "defi")]
  [string]$AssetClass = "crypto",
  [string]$Strategy = "council",
  [string]$Interval = "1m",
  [int]$StartupWaitSec = 8
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
  New-Item -ItemType Directory -Force -Path $runDir | Out-Null

  $pythonBin = Join-Path $RepoPath "venv\Scripts\python.exe"
  $daemonEntry = Join-Path $RepoPath "Scripts\paper_daemon.py"
  if (-not (Test-Path $daemonEntry)) {
    $daemonEntry = Join-Path $RepoPath "scripts\paper_daemon.py"
  }
  if (-not (Test-Path $pythonBin)) {
    throw "python bulunamadi: $pythonBin"
  }
  if (-not (Test-Path $daemonEntry)) {
    throw "paper_daemon.py bulunamadi"
  }

  $pidFile = Join-Path $runDir "daemon.pid"
  $logFile = Join-Path $runDir "daemon.log"
  $errFile = Join-Path $runDir "daemon.err.log"
  if (-not (Test-Path $logFile)) { New-Item -ItemType File -Path $logFile | Out-Null }
  if (-not (Test-Path $errFile)) { New-Item -ItemType File -Path $errFile | Out-Null }

  if (Test-Path $pidFile) {
    $pidRaw = (Get-Content -Path $pidFile -Raw -ErrorAction SilentlyContinue)
    $oldPid = 0
    if ($pidRaw) { [void][int]::TryParse($pidRaw.Trim(), [ref]$oldPid) }
    if ($oldPid -gt 0 -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
      Write-Host "[windows_soak_start] already running pid=$oldPid asset=$AssetClass"
      Write-Host "[windows_soak_start] next: windows_soak_status.ps1 -AssetClass $AssetClass"
      exit 0
    }
    Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
  }

  Add-Content -Path $logFile -Value @(
    "",
    "============================================================",
    "[windows_soak_start] $([DateTimeOffset]::UtcNow.ToString('o'))",
    "asset_class=$AssetClass",
    "run_dir=$runDir",
    "============================================================"
  )

  $daemonId = "YEAR2_$($AssetClass.ToUpper())_WIN"
  $args = @(
    $daemonEntry,
    "--daemon_id", $daemonId,
    "--run_dir", $runDir,
    "--strategy", $Strategy,
    "--interval", $Interval,
    "--mode", "v2",
    "--asset-class", $AssetClass,
    "--venue-id", "auto"
  )

  $proc = Start-Process `
    -FilePath $pythonBin `
    -ArgumentList $args `
    -WorkingDirectory $RepoPath `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errFile `
    -PassThru `
    -WindowStyle Hidden

  Set-Content -Path $pidFile -Value $proc.Id -NoNewline
  Start-Sleep -Seconds $StartupWaitSec

  $live = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if (-not $live) {
    Write-Host "[windows_soak_start] ERROR: daemon ayakta kalmadi (pid=$($proc.Id))"
    if (Test-Path $logFile) { Get-Content -Path $logFile -Tail 40 }
    if (Test-Path $errFile) { Get-Content -Path $errFile -Tail 40 }
    Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
    exit 1
  }

  Write-Host "[windows_soak_start] started"
  Write-Host "  pid=$($proc.Id)"
  Write-Host "  asset_class=$AssetClass"
  Write-Host "  run_dir=$runDir"
  Write-Host "  log=$logFile"
  Write-Host "Next:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\windows_soak_status.ps1 -RootPath `"$RootPath`" -AssetClass $AssetClass"
  exit 0
} catch {
  Write-Host "[windows_soak_start] FAILED: $($_.Exception.Message)"
  exit 1
}

