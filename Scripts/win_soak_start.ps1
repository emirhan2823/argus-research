# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$Strategy = "council",
  [string]$RunDir = "runs/year2/paper_main",
  [string]$DaemonId = "YEAR2_SOAK_WIN",
  [int]$StartupWaitSec = 3,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $PSBoundParameters.ContainsKey("RunDir") -and $env:ARGUS_RUN_DIR) {
  $RunDir = $env:ARGUS_RUN_DIR
}

if (-not $PSBoundParameters.ContainsKey("StartupWaitSec") -and $env:ARGUS_STARTUP_WAIT_SEC) {
  $parsedWaitSec = 0
  if ([int]::TryParse($env:ARGUS_STARTUP_WAIT_SEC, [ref]$parsedWaitSec) -and $parsedWaitSec -gt 0) {
    $StartupWaitSec = $parsedWaitSec
  }
}

$PythonBin = if ($env:ARGUS_PYTHON_BIN) { $env:ARGUS_PYTHON_BIN } else { Join-Path $RepoRoot "venv\Scripts\python.exe" }
$DaemonEntrypoint = if ($env:ARGUS_DAEMON_ENTRYPOINT) { $env:ARGUS_DAEMON_ENTRYPOINT } else { Join-Path $RepoRoot "Scripts\paper_daemon.py" }

if (-not [System.IO.Path]::IsPathRooted($PythonBin)) {
  $PythonBin = Join-Path $RepoRoot $PythonBin
}
$PythonBin = [System.IO.Path]::GetFullPath($PythonBin)

if (-not [System.IO.Path]::IsPathRooted($DaemonEntrypoint)) {
  $DaemonEntrypoint = Join-Path $RepoRoot $DaemonEntrypoint
}
$DaemonEntrypoint = [System.IO.Path]::GetFullPath($DaemonEntrypoint)

if (-not (Test-Path $DaemonEntrypoint)) {
  $AltEntrypoint = Join-Path $RepoRoot "scripts\paper_daemon.py"
  if (Test-Path $AltEntrypoint) {
    $DaemonEntrypoint = $AltEntrypoint
  }
}

if (-not (Test-Path $PythonBin)) {
  Write-Host "[win_soak_start] ERROR: python bulunamadi: $PythonBin"
  Write-Host "[win_soak_start] ACTION:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\win_prepare.ps1"
  exit 1
}

if (-not (Test-Path $DaemonEntrypoint)) {
  Write-Host "[win_soak_start] ERROR: daemon entrypoint bulunamadi"
  Write-Host "  checked: $(Join-Path $RepoRoot 'Scripts\paper_daemon.py')"
  Write-Host "  checked: $(Join-Path $RepoRoot 'scripts\paper_daemon.py')"
  exit 1
}

if (-not [System.IO.Path]::IsPathRooted($RunDir)) {
  $RunDir = Join-Path $RepoRoot $RunDir
}
$RunDir = [System.IO.Path]::GetFullPath($RunDir)

$PidFile = if ($env:ARGUS_PID_FILE) { $env:ARGUS_PID_FILE } else { Join-Path $RunDir "daemon.pid" }
$LogFile = if ($env:ARGUS_LOG_FILE) { $env:ARGUS_LOG_FILE } else { Join-Path $RunDir "daemon.log" }
$ErrFile = if ($env:ARGUS_ERR_LOG_FILE) { $env:ARGUS_ERR_LOG_FILE } else { Join-Path $RunDir "daemon.err.log" }

if (-not [System.IO.Path]::IsPathRooted($PidFile)) {
  $PidFile = Join-Path $RepoRoot $PidFile
}
$PidFile = [System.IO.Path]::GetFullPath($PidFile)

if (-not [System.IO.Path]::IsPathRooted($LogFile)) {
  $LogFile = Join-Path $RepoRoot $LogFile
}
$LogFile = [System.IO.Path]::GetFullPath($LogFile)

if (-not [System.IO.Path]::IsPathRooted($ErrFile)) {
  $ErrFile = Join-Path $RepoRoot $ErrFile
}
$ErrFile = [System.IO.Path]::GetFullPath($ErrFile)

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
if (-not (Test-Path $LogFile)) { New-Item -ItemType File -Path $LogFile | Out-Null }
if (-not (Test-Path $ErrFile)) { New-Item -ItemType File -Path $ErrFile | Out-Null }

if (Test-Path $PidFile) {
  $ExistingPidRaw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue)
  $ExistingPid = 0
  if ($ExistingPidRaw) {
    [void][int]::TryParse($ExistingPidRaw.Trim(), [ref]$ExistingPid)
  }
  if ($ExistingPid -gt 0) {
    $ExistingProc = Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
    if ($ExistingProc) {
      Write-Host "[win_soak_start] already running (pid=$ExistingPid)"
      exit 0
    }
  }
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
}

$Banner = @(
  "",
  "============================================================",
  "[win_soak_start] $([DateTime]::UtcNow.ToString('o'))",
  "run_dir=$RunDir",
  "pid_file=$PidFile",
  "strategy=$Strategy",
  "============================================================"
) -join [Environment]::NewLine
Add-Content -Path $LogFile -Value $Banner

$Args = @(
  $DaemonEntrypoint,
  "--daemon_id", $DaemonId,
  "--run_dir", $RunDir,
  "--strategy", $Strategy
)
if ($ExtraArgs) {
  $Args += $ExtraArgs
}
Add-Content -Path $LogFile -Value ("[win_soak_start] cmd={0} {1}" -f $PythonBin, ($Args -join " "))

$Proc = Start-Process `
  -FilePath $PythonBin `
  -ArgumentList $Args `
  -WorkingDirectory $RepoRoot `
  -RedirectStandardOutput $LogFile `
  -RedirectStandardError $ErrFile `
  -PassThru `
  -WindowStyle Hidden

Set-Content -Path $PidFile -Value $Proc.Id -NoNewline
Start-Sleep -Seconds $StartupWaitSec

$LiveProc = Get-Process -Id $Proc.Id -ErrorAction SilentlyContinue
if (-not $LiveProc) {
  Write-Host "[win_soak_start] ERROR: daemon ayakta kalmadi (pid=$($Proc.Id))"
  Write-Host "[win_soak_start] last daemon.log:"
  if (Test-Path $LogFile) { Get-Content -Path $LogFile -Tail 60 }
  Write-Host "[win_soak_start] last daemon.err.log:"
  if (Test-Path $ErrFile) { Get-Content -Path $ErrFile -Tail 60 }
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  exit 1
}

Write-Host "[win_soak_start] started"
Write-Host "  pid=$($Proc.Id)"
Write-Host "  strategy=$Strategy"
Write-Host "  run_dir=$RunDir"
Write-Host "  log=$LogFile"
Write-Host "  err=$ErrFile"
