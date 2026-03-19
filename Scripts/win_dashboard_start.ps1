# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RunDir = "runs/year2/paper_main",
  [string]$Host = "127.0.0.1",
  [int]$Port = 18081
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not [System.IO.Path]::IsPathRooted($RunDir)) {
  $RunDir = Join-Path $RepoRoot $RunDir
}
$RunDir = [System.IO.Path]::GetFullPath($RunDir)

$PythonBin = Join-Path $RepoRoot "venv\Scripts\python.exe"
$DashboardScript = Join-Path $RepoRoot "Scripts\dashboard.py"

if (-not (Test-Path $PythonBin)) {
  Write-Host "[win_dashboard_start] ERROR: python bulunamadi: $PythonBin"
  exit 1
}
if (-not (Test-Path $DashboardScript)) {
  Write-Host "[win_dashboard_start] ERROR: dashboard script bulunamadi: $DashboardScript"
  exit 1
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$PidFile = Join-Path $RunDir "dashboard.pid"
$LogFile = Join-Path $RunDir "dashboard.log"
$ErrFile = Join-Path $RunDir "dashboard.err.log"
if (-not (Test-Path $LogFile)) { New-Item -ItemType File -Path $LogFile | Out-Null }
if (-not (Test-Path $ErrFile)) { New-Item -ItemType File -Path $ErrFile | Out-Null }

if (Test-Path $PidFile) {
  $oldRaw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue)
  $oldPid = 0
  if ($oldRaw) { [void][int]::TryParse($oldRaw.Trim(), [ref]$oldPid) }
  if ($oldPid -gt 0 -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
    Write-Host "[win_dashboard_start] already running (pid=$oldPid)"
    exit 0
  }
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
}

$Args = @($DashboardScript, $RunDir, "--host", $Host, "--port", "$Port")
$Proc = Start-Process `
  -FilePath $PythonBin `
  -ArgumentList $Args `
  -WorkingDirectory $RepoRoot `
  -RedirectStandardOutput $LogFile `
  -RedirectStandardError $ErrFile `
  -PassThru `
  -WindowStyle Hidden

Set-Content -Path $PidFile -Value $Proc.Id -NoNewline
Start-Sleep -Seconds 2

if (-not (Get-Process -Id $Proc.Id -ErrorAction SilentlyContinue)) {
  Write-Host "[win_dashboard_start] ERROR: dashboard ayakta kalmadi (pid=$($Proc.Id))"
  if (Test-Path $LogFile) { Get-Content -Path $LogFile -Tail 40 }
  if (Test-Path $ErrFile) { Get-Content -Path $ErrFile -Tail 40 }
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  exit 1
}

Write-Host "[win_dashboard_start] started"
Write-Host "  pid=$($Proc.Id)"
Write-Host "  url=http://$Host`:$Port"
Write-Host "  run_dir=$RunDir"
