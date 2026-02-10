# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RootPath = "E:\argus",
  [string]$RepoPath = "",
  [ValidateSet("crypto", "stock", "defi")]
  [string]$AssetClass = "crypto",
  [string]$Strategy = "council",
  [string]$Interval = "1m",
  [int]$DurationSec = 180
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

function Get-GitCommit {
  param([string]$Repo)
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return "unknown" }
  if (-not (Test-Path (Join-Path $Repo ".git"))) { return "unknown" }
  Push-Location $Repo
  try {
    $v = (& git rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { return "unknown" }
    return ($v | Out-String).Trim()
  } finally {
    Pop-Location
  }
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

try {
  $RootPath = [System.IO.Path]::GetFullPath($RootPath)
  $RepoPath = Resolve-RepoPath -Root $RootPath -Repo $RepoPath
  $pythonBin = Join-Path $RepoPath "venv\Scripts\python.exe"
  $nightlyScript = Join-Path $RepoPath "Scripts\nightly_eval.py"
  if (-not (Test-Path $pythonBin)) { throw "venv python bulunamadi: $pythonBin" }
  if (-not (Test-Path $nightlyScript)) { throw "nightly_eval.py bulunamadi: $nightlyScript" }

  $runDir = Join-Path $RootPath "runs\year2\paper_main_$AssetClass"
  New-Item -ItemType Directory -Force -Path $runDir | Out-Null
  $reportPath = Join-Path $RepoPath "reports\year2\windows_sprint_b_validation.md"
  Ensure-ValidationTemplate -ReportPath $reportPath
  $commit = Get-GitCommit -Repo $RepoPath
  $ts = [DateTimeOffset]::UtcNow.ToString("o")

  $startScript = Join-Path $PSScriptRoot "windows_soak_start.ps1"
  $statusScript = Join-Path $PSScriptRoot "windows_soak_status.ps1"
  $stopScript = Join-Path $PSScriptRoot "windows_soak_stop.ps1"

  & $startScript -RootPath $RootPath -RepoPath $RepoPath -AssetClass $AssetClass -Strategy $Strategy -Interval $Interval
  $startExit = $LASTEXITCODE
  if ($startExit -ne 0) { throw "windows_soak_start failed exit=$startExit" }

  Write-Host "[windows_run_sprint_b] soak running for $DurationSec seconds..."
  Start-Sleep -Seconds $DurationSec

  & $statusScript -RootPath $RootPath -RepoPath $RepoPath -AssetClass $AssetClass
  $statusExit = $LASTEXITCODE

  & $stopScript -RootPath $RootPath -RepoPath $RepoPath -AssetClass $AssetClass
  $stopExit = $LASTEXITCODE

  $reportsDir = Join-Path $RepoPath "reports\year2\windows\$AssetClass"
  New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null
  Push-Location $RepoPath
  try {
    $nightlyOutput = & $pythonBin $nightlyScript --mode v2 --run_dir $runDir --reports_dir $reportsDir 2>&1
    $nightlyExit = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  $nightlyText = ($nightlyOutput | Out-String).Trim()

  $hbPath = Join-Path $runDir "heartbeat.json"
  $metricsPath = Join-Path $runDir "metrics.json"
  $barsSeen = 0
  $decisions = 0
  $trades = 0
  $rejects = 0
  $mode = "unknown"
  $venue = "unknown"

  if (Test-Path $metricsPath) {
    $m = Get-Content -Path $metricsPath -Raw | ConvertFrom-Json
    $barsSeen = [int]$m.bars_seen
    $decisions = [int]$m.decisions_total
    $trades = [int]$m.trades_total
    $rejects = [int]$m.rejects_total
    $mode = [string]$m.mode
    $venue = [string]$m.venue_id
  }

  $summaryPass = ($startExit -eq 0 -and $stopExit -eq 0 -and $nightlyExit -eq 0 -and (Test-Path $hbPath) -and $barsSeen -gt 0)
  $resultText = if ($summaryPass) { "PASS" } else { "FAIL" }

  Add-Content -Path $reportPath -Value @"
## Sprint-B Asset Run - $ts
- AssetClass: `$AssetClass`
- RootPath: `$RootPath`
- RepoPath: `$RepoPath`
- RunDir: `$runDir`
- Git Commit: `$commit`
- StartExit: $startExit
- StatusExit: $statusExit
- StopExit: $stopExit
- NightlyExit: $nightlyExit
- Mode: `$mode`
- Venue: `$venue`
- Counters: bars=$barsSeen decisions=$decisions trades=$trades rejects=$rejects
- Result: **$resultText**

```text
$nightlyText
```

"@

  if (-not $summaryPass) {
    Write-Host "[windows_run_sprint_b] FAILED"
    Write-Host "Validation report: $reportPath"
    exit 1
  }

  Write-Host "[windows_run_sprint_b] PASS"
  Write-Host "Validation report: $reportPath"
  Write-Host "Next:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File Scripts\windows_run_sprint_b.ps1 -RootPath `"$RootPath`" -AssetClass stock"
  exit 0
} catch {
  Write-Host "[windows_run_sprint_b] FAILED: $($_.Exception.Message)"
  exit 1
}

