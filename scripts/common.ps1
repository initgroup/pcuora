$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
$Manage = Join-Path $ProjectRoot 'deploy/manage.py'
$Runtime = Join-Path $ProjectRoot 'runtime'
function Require-Python {
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Run scripts/setup.ps1 first.' }
}
function Use-Profile([string]$Profile) {
    $env:OML_ENV_FILE = Join-Path $ProjectRoot "security/$Profile.env"
    if (-not (Test-Path -LiteralPath $env:OML_ENV_FILE)) { throw "Missing security/$Profile.env. Follow the setup guide." }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
}
