. "$PSScriptRoot/common.ps1"
$statePath = Join-Path $Runtime 'service.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Host 'No tracked server.'; exit 0 }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
if ($process) {
    if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.startTicks) { throw 'PID was reused. Refusing to stop an unrelated process.' }
    $details = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.pid)"
    if (-not $details.CommandLine -or -not $details.CommandLine.Contains($Manage)) { throw 'Command line does not match this project. Refusing to stop.' }
    Stop-Process -Id $state.pid
    Write-Host 'OML Classroom stopped.'
} else { Write-Host 'Tracked server is already stopped.' }
Remove-Item -LiteralPath $statePath
