. "$PSScriptRoot/common.ps1"
Require-Python
& $Python (Join-Path $PSScriptRoot 'source_backup.py') folder
if ($LASTEXITCODE -ne 0) { throw 'Source backup failed.' }
