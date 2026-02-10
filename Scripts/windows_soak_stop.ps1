# ARGUS CORE INFRA - DO NOT DELETE
param(
  [string]$RootPath = "E:\argus",
  [string]$RepoPath = "",
  [ValidateSet("crypto", "stock", "defi")]
  [string]$AssetClass = "crypto",
  [int]$GracePeriodSec = 12
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

  if (-not (Test-Path $pidFile)) {
    Write-Host "[windows_soak_stop] pidfile yok ($pidFile)"
    exit 0
  }

  $pidRaw = (Get-Content -Path $pidFile -Raw -ErrorAction SilentlyContinue)
  $pidValue = 0
  if (-not $pidRaw -or -not [int]::TryParse($pidRaw.Trim(), [ref]$pidValue)) {
    Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "[windows_soak_stop] invalid pidfile temizlendi"
    exit 0
  }

  $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
  if ($proc) {
    Write-Host "[windows_soak_stop] stopping pid=$pidValue asset=$AssetClass"
    Stop-Process -Id $pidValue -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt ($GracePeriodSec * 2); $i++) {
      Start-Sleep -Milliseconds 500
      if (-not (Get-Process -Id $pidValue -ErrorAction SilentlyContinue)) {
        break
      }
    }
    if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
      Write-Host "[windows_soak_stop] forcing kill pid=$pidValue"
      Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    }
  } else {
    Write-Host "[windows_soak_stop] stale pid=$pidValue"
  }

  Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
  Write-Host "[windows_soak_stop] pidfile cleaned"
  exit 0
} catch {
  Write-Host "[windows_soak_stop] FAILED: $($_.Exception.Message)"
  exit 1
}

