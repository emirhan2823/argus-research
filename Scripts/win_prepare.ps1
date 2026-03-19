# ARGUS CORE INFRA - DO NOT DELETE
param(
  [switch]$WithDevDeps,
  [switch]$WithUiDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$VenvDir = Join-Path $RepoRoot "venv"
$PythonBin = Join-Path $VenvDir "Scripts\python.exe"

function Require-PythonLauncher {
  if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "[win_prepare] ERROR: 'py' launcher bulunamadi."
    Write-Host "[win_prepare] ACTION: Python 3.11+ kur (https://www.python.org/downloads/windows/)"
    exit 1
  }
}

function Run-Step([string]$Description, [scriptblock]$Step) {
  Write-Host "[win_prepare] $Description"
  & $Step
}

Require-PythonLauncher

if (-not (Test-Path $PythonBin)) {
  Run-Step "venv olusturuluyor..." { py -3 -m venv $VenvDir }
}

if (-not (Test-Path $PythonBin)) {
  Write-Host "[win_prepare] ERROR: venv python olusturulamadi: $PythonBin"
  exit 1
}

Run-Step "pip guncelleniyor..." { & $PythonBin -m pip install --upgrade pip }
Run-Step "runtime bagimliliklar kuruluyor..." { & $PythonBin -m pip install -r (Join-Path $RepoRoot "requirements.txt") }

if ($WithDevDeps) {
  Run-Step "dev bagimliliklar kuruluyor..." { & $PythonBin -m pip install -r (Join-Path $RepoRoot "requirements-dev.txt") }
}

if ($WithUiDeps) {
  $UiReq = Join-Path $RepoRoot "requirements_phase19_ui.txt"
  if (Test-Path $UiReq) {
    Run-Step "ui bagimliliklar kuruluyor..." { & $PythonBin -m pip install -r $UiReq }
  } else {
    Write-Host "[win_prepare] WARNING: ui requirements bulunamadi: $UiReq"
  }
}

Write-Host ""
Write-Host "[win_prepare] OK"
Write-Host "Repo: $RepoRoot"
Write-Host "Python: $PythonBin"
Write-Host ""
Write-Host "Next:"
Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\win_soak_start.ps1 -Strategy council"
Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\win_soak_status.ps1"
