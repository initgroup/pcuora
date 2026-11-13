# Workspace terminal entry point. Runs in the new terminal process itself.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$activate = Join-Path $ProjectRoot '.venv/Scripts/Activate.ps1'
if (Test-Path -LiteralPath $activate) {
    . $activate
    Write-Host 'OML project environment is active.' -ForegroundColor Green
    python --version
    Write-Host 'Check: python -c "import sys; print(sys.executable)"'
} else {
    Write-Host 'First run: powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1' -ForegroundColor Yellow
    Write-Host 'Then close this terminal and open a new OML (.venv) terminal.'
}
