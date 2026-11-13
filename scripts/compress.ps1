. "$PSScriptRoot/common.ps1"
Require-Python
& $Python (Join-Path $PSScriptRoot 'source_backup.py') zip
if ($LASTEXITCODE -ne 0) { throw 'Source compression failed.' }
