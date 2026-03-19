param(
    [switch]$ForwardSim,
    [switch]$Smoke,
    [int]$Cycles = 240,
    [string]$ReplayAnchor = "",
    [string]$Symbols = "BTCUSDT"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

Set-Location $repoRoot

$argsList = @("scripts/war_forward_report.py")
if ($ForwardSim) {
    $argsList += "--forward-sim"
}
if ($Smoke) {
    $argsList += "--smoke"
}
if ($Cycles -gt 0) {
    $argsList += "--cycles"
    $argsList += "$Cycles"
}
if ($ReplayAnchor -ne "") {
    $argsList += "--replay-anchor"
    $argsList += $ReplayAnchor
}
if ($Symbols -ne "") {
    $argsList += "--symbols"
    $argsList += $Symbols
}

python @argsList
exit $LASTEXITCODE
