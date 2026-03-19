# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RootPath = "E:\argus",
  [string]$RepoPath = "",
  [string]$GitUrl = "",
  [string]$PythonSpec = "3.11",
  [switch]$SkipDevDeps
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

function Ensure-Dir {
  param([string]$PathValue)
  New-Item -ItemType Directory -Force -Path $PathValue | Out-Null
}

function New-Or-UpdateVenv {
  param([string]$Repo, [string]$Spec)
  $venvDir = Join-Path $Repo "venv"
  $pythonBin = Join-Path $venvDir "Scripts\python.exe"
  if (Test-Path $pythonBin) {
    return $pythonBin
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py "-$Spec" -m venv $venvDir
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $venvDir
  } else {
    throw "Python launcher bulunamadi. py veya python komutu gerekli."
  }

  if (-not (Test-Path $pythonBin)) {
    throw "venv olusturulamadi: $pythonBin"
  }
  return $pythonBin
}

function Install-Dependencies {
  param([string]$Repo, [string]$PythonBin, [bool]$UseDev)
  & $PythonBin -m pip install --upgrade pip
  & $PythonBin -m pip install -r (Join-Path $Repo "requirements.txt")
  if ($UseDev -and (Test-Path (Join-Path $Repo "requirements-dev.txt"))) {
    & $PythonBin -m pip install -r (Join-Path $Repo "requirements-dev.txt")
  }
}

try {
  $RootPath = [System.IO.Path]::GetFullPath($RootPath)
  $RepoPath = Resolve-RepoPath -Root $RootPath -Repo $RepoPath

  Ensure-Dir -PathValue $RootPath
  Ensure-Dir -PathValue (Join-Path $RootPath "runs")
  Ensure-Dir -PathValue (Join-Path $RootPath "runs\year2")
  foreach ($asset in @("crypto", "stock", "defi")) {
    Ensure-Dir -PathValue (Join-Path $RootPath "runs\year2\paper_main_$asset")
  }

  if (-not (Test-Path $RepoPath)) {
    if ($GitUrl -and $GitUrl.Trim().Length -gt 0) {
      Ensure-Dir -PathValue $RootPath
      & git clone $GitUrl $RepoPath
    } else {
      Write-Host "[windows_setup] ERROR: repo bulunamadi: $RepoPath"
      Write-Host "[windows_setup] Clone adimi:"
      Write-Host "  git clone <REPO_URL> `"$RepoPath`""
      exit 2
    }
  }

  $pythonBin = New-Or-UpdateVenv -Repo $RepoPath -Spec $PythonSpec
  Install-Dependencies -Repo $RepoPath -PythonBin $pythonBin -UseDev:(-not $SkipDevDeps.IsPresent)

  $reportPath = Join-Path $RepoPath "reports\year2\windows_sprint_b_validation.md"
  $reportDir = Split-Path -Parent $reportPath
  Ensure-Dir -PathValue $reportDir
  if (-not (Test-Path $reportPath)) {
    @(
      "# Windows Sprint-B Validation Report",
      "",
      "- This file is appended by `Scripts/windows_doctor.ps1` and `Scripts/windows_run_sprint_b.ps1`.",
      "- Workspace root default: `E:\\argus`.",
      ""
    ) | Set-Content -Path $reportPath -Encoding UTF8
  }

  Write-Host "[windows_setup] OK"
  Write-Host "  RootPath : $RootPath"
  Write-Host "  RepoPath : $RepoPath"
  Write-Host "  Python   : $pythonBin"
  Write-Host "  RunDirs  : $(Join-Path $RootPath 'runs\year2\paper_main_{crypto|stock|defi}')"
  Write-Host ""
  Write-Host "Next:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\windows_doctor.ps1 -RootPath `"$RootPath`""
  exit 0
} catch {
  Write-Host "[windows_setup] FAILED: $($_.Exception.Message)"
  exit 1
}

