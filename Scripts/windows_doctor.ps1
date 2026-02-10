# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RootPath = "E:\argus",
  [string]$RepoPath = "",
  [string]$PythonSpec = "3.11"
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

function Ensure-ValidationTemplate {
  param([string]$ReportPath)
  $dir = Split-Path -Parent $ReportPath
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  if (-not (Test-Path $ReportPath)) {
    @(
      "# Windows Sprint-B Validation Report",
      "",
      "- Auto-generated append-only validation log.",
      ""
    ) | Set-Content -Path $ReportPath -Encoding UTF8
  }
}

function Get-GitCommit {
  param([string]$Repo)
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    return "unknown"
  }
  if (-not (Test-Path (Join-Path $Repo ".git"))) {
    return "unknown"
  }
  Push-Location $Repo
  try {
    $commit = (& git rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) {
      return "unknown"
    }
    return ($commit | Out-String).Trim()
  } finally {
    Pop-Location
  }
}

try {
  $RootPath = [System.IO.Path]::GetFullPath($RootPath)
  $RepoPath = Resolve-RepoPath -Root $RootPath -Repo $RepoPath
  $setupScript = Join-Path $PSScriptRoot "windows_setup.ps1"
  & $setupScript -RootPath $RootPath -RepoPath $RepoPath -PythonSpec $PythonSpec
  if ($LASTEXITCODE -ne 0) {
    throw "windows_setup failed with exit code $LASTEXITCODE"
  }

  $pythonBin = Join-Path $RepoPath "venv\Scripts\python.exe"
  if (-not (Test-Path $pythonBin)) {
    throw "venv python bulunamadi: $pythonBin"
  }

  Push-Location $RepoPath
  try {
    $pytestOutput = & $pythonBin -m pytest -q 2>&1
    $pytestExit = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  $pytestText = ($pytestOutput | Out-String).Trim()

  $reportPath = Join-Path $RepoPath "reports\year2\windows_sprint_b_validation.md"
  Ensure-ValidationTemplate -ReportPath $reportPath
  $commit = Get-GitCommit -Repo $RepoPath
  $ts = [DateTimeOffset]::UtcNow.ToString("o")
  $resultText = if ($pytestExit -eq 0) { "PASS" } else { "FAIL" }

  Add-Content -Path $reportPath -Value @"
## Doctor Run - $ts
- RootPath: `$RootPath`
- RepoPath: `$RepoPath`
- Git Commit: `$commit`
- Command: `venv\Scripts\python.exe -m pytest -q`
- ExitCode: $pytestExit
- Result: **$resultText**

```text
$pytestText
```

"@

  if ($pytestExit -ne 0) {
    Write-Host "[windows_doctor] FAILED (pytest exit=$pytestExit)"
    Write-Host "Validation report: $reportPath"
    exit $pytestExit
  }

  Write-Host "[windows_doctor] PASS"
  Write-Host "Validation report: $reportPath"
  Write-Host "Next:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\windows_run_sprint_b.ps1 -RootPath `"$RootPath`" -AssetClass crypto"
  exit 0
} catch {
  Write-Host "[windows_doctor] FAILED: $($_.Exception.Message)"
  exit 1
}

