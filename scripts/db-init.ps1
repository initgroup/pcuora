param([ValidateSet('student','teacher')][string]$Profile='student')
. "$PSScriptRoot/common.ps1"
Require-Python
Use-Profile $Profile
& $Python $Manage check
if ($LASTEXITCODE -ne 0) { throw 'Connection check failed.' }
& $Python $Manage init
if ($LASTEXITCODE -ne 0) { throw 'Schema initialization failed.' }
