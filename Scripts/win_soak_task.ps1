# ARGUS CORE INFRA - DO NOT DELETE
param(
  [ValidateSet("install", "start", "stop", "status", "remove")]
  [string]$Action = "status",
  [string]$TaskName = "ArgusPaperSoak",
  [string]$Strategy = "council",
  [string]$RunDir = "runs/year2/paper_main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$StartScript = Join-Path $RepoRoot "Scripts\win_soak_start.ps1"
$PsExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $StartScript)) {
  Write-Host "[win_soak_task] ERROR: start script bulunamadi: $StartScript"
  exit 1
}

function Install-Task {
  Import-Module ScheduledTasks
  $argText = "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`" -Strategy `"$Strategy`" -RunDir `"$RunDir`""
  $taskAction = New-ScheduledTaskAction -Execute $PsExe -Argument $argText -WorkingDirectory $RepoRoot
  $triggers = @(
    New-ScheduledTaskTrigger -AtStartup
    New-ScheduledTaskTrigger -AtLogOn
  )
  $settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $triggers -Settings $settings -Description "Argus paper soak auto-start" -Force | Out-Null
  Write-Host "[win_soak_task] installed: $TaskName"
}

function Start-TaskNow {
  Start-ScheduledTask -TaskName $TaskName
  Write-Host "[win_soak_task] started: $TaskName"
}

function Stop-TaskNow {
  Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  Write-Host "[win_soak_task] stopped: $TaskName"
}

function Show-TaskStatus {
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if (-not $task) {
    Write-Host "[win_soak_task] not found: $TaskName"
    return
  }
  $info = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Host "[win_soak_task] name: $TaskName"
  Write-Host "[win_soak_task] state: $($task.State)"
  Write-Host "[win_soak_task] last run: $($info.LastRunTime)"
  Write-Host "[win_soak_task] last result: $($info.LastTaskResult)"
  Write-Host "[win_soak_task] next run: $($info.NextRunTime)"
}

function Remove-Task {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "[win_soak_task] removed: $TaskName"
}

switch ($Action) {
  "install" { Install-Task }
  "start" { Start-TaskNow }
  "stop" { Stop-TaskNow }
  "status" { Show-TaskStatus }
  "remove" { Remove-Task }
}
