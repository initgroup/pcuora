param([string]$PythonExe = '')
. "$PSScriptRoot/common.ps1"
if (-not (Test-Path -LiteralPath $Python)) {
    $candidates = @($PythonExe, "$env:LOCALAPPDATA/Programs/Python/Python312/python.exe", 'C:/Program Files/Python312/python.exe')
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $selected = $null
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $version = & $candidate -c "import sys; print('.'.join(map(str,sys.version_info[:2])))"
            if ($version -eq '3.12') { $selected = $candidate; break }
        }
    }
    if (-not $selected) { throw 'Install Python 3.12 (64-bit) from reference/installers, or pass -PythonExe C:/path/python.exe.' }
    & $selected -m venv (Join-Path $ProjectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
$version = & $Python -c "import sys,struct; print(str(sys.version_info[:2]==(3,12) and struct.calcsize('P')==8))"
if ($version -ne 'True') { throw 'This package needs a Python 3.12 64-bit virtual environment.' }
$lock = Join-Path $ProjectRoot 'reference/requirements.lock'
$wheels = Join-Path $ProjectRoot 'reference/wheels'
if (Test-Path -LiteralPath $wheels) {
    & $Python -m pip install --no-index --find-links $wheels -r $lock
} else {
    & $Python -m pip install -r $lock
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the Python version and wheel files.' }
$clientZip = Join-Path $ProjectRoot 'reference/installers/instantclient-basiclite-windows.x64-23.26.4.0.0.zip'
$clientDest = Join-Path $ProjectRoot 'runtime/instantclient'
if (Test-Path -LiteralPath $clientZip) {
    $hash=(Get-FileHash -LiteralPath $clientZip -Algorithm SHA256).Hash
    if ($hash -ne '7586c02a2926f619a0b16a9ae32e85bb3605798aa177155b065fffb48a1ee0b8') { throw 'Instant Client checksum mismatch.' }
    if (-not (Test-Path -LiteralPath (Join-Path $clientDest 'instantclient_23_26/oci.dll'))) {
        Expand-Archive -LiteralPath $clientZip -DestinationPath $clientDest -Force
    }
    Write-Host 'Bundled Oracle Client ready. If DPI-1047 occurs, check the client path and x64 architecture first. Install/update the VC++ x64 runtime only if missing or incompatible; see the web setup guide.'
}
$student = Join-Path $ProjectRoot 'security/student.env'
if (-not (Test-Path -LiteralPath $student)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'security/student.env.example') -Destination $student
}
Write-Host 'Ready. Edit security/student.env, then run scripts/db-init.ps1 and scripts/start.ps1.'
