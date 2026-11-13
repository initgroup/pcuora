. "$PSScriptRoot/common.ps1"
Require-Python
& $Python (Join-Path $PSScriptRoot 'package_student.py')
if ($LASTEXITCODE -ne 0) { throw 'Student packaging failed.' }
