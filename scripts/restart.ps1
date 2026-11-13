param([ValidateSet('student','teacher')][string]$Profile='', [int]$Port=0)
. "$PSScriptRoot/common.ps1"
$statePath=Join-Path $Runtime 'service.json'
if (Test-Path -LiteralPath $statePath) {
    $state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    if (-not $Profile) { $Profile=$state.profile }
    if (-not $Port) { $Port=$state.port }
}
if (-not $Profile) { $Profile='student' }
if (-not $Port) { $Port=22417 }
& "$PSScriptRoot/stop.ps1"
& "$PSScriptRoot/start.ps1" -Profile $Profile -Port $Port
