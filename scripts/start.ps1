param([ValidateSet('student','teacher')][string]$Profile='student', [ValidateRange(1024,65535)][int]$Port=22417)
. "$PSScriptRoot/common.ps1"
Require-Python
Use-Profile $Profile
New-Item -ItemType Directory -Path $Runtime -Force | Out-Null
$statePath = Join-Path $Runtime 'service.json'
if (Test-Path -LiteralPath $statePath) {
    $old = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $running = Get-Process -Id $old.pid -ErrorAction SilentlyContinue
    if ($running -and $running.StartTime.ToUniversalTime().Ticks.ToString() -eq $old.startTicks) {
        Write-Host "Already running: http://127.0.0.1:$($old.port)"
        exit 0
    }
}
$probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
try { $probe.Start() } catch { throw "Port $Port is in use. Pass -Port 22418 or stop the existing server." } finally { $probe.Stop() }
$argsList = @(('"' + $Manage + '"'), 'serve', '--port', $Port.ToString())
$proc = Start-Process -FilePath $Python -ArgumentList $argsList -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Runtime 'server.out.log') -RedirectStandardError (Join-Path $Runtime 'server.err.log')
$state = @{pid=$proc.Id; startTicks=$proc.StartTime.ToUniversalTime().Ticks.ToString(); port=$Port; profile=$Profile; root=$ProjectRoot}
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
$ready=$false
for ($attempt=0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    if ($proc.HasExited) { throw 'Web process exited. See runtime/server.err.log.' }
    try { $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2; if ($response.StatusCode -eq 200) { $ready=$true; break } } catch {}
}
if (-not $ready) { throw 'Server readiness timed out. See runtime/server.err.log.' }
Write-Host "OML Classroom is ready: http://127.0.0.1:$Port"
Write-Host "Profile: $Profile. Stop with scripts/stop.ps1."
