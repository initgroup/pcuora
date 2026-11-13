param([ValidateSet('student','teacher')][string]$Profile='student')
. "$PSScriptRoot/common.ps1"
Require-Python
Use-Profile $Profile
& $Python $Manage verify
if ($LASTEXITCODE -ne 0) { throw 'Database verification failed.' }
