[CmdletBinding()]
param([string]$StudentId='', [string]$Output='')
. "$PSScriptRoot/common.ps1"
Require-Python
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
# A verified ZIP replaces the previous download; no dated release directories.
# Resolve optional relative destinations from this script's project root.
if ($Output -and -not [IO.Path]::IsPathRooted($Output)) {
    $Output=Join-Path $ProjectRoot $Output
}
$packageArgs=@((Join-Path $PSScriptRoot 'package_student.py'),'--replace')
if ($StudentId) { $packageArgs+=@('--student-id',$StudentId) }
if ($Output) { $packageArgs+=@('--output',$Output) }
& $Python @packageArgs
if ($LASTEXITCODE -ne 0) { throw 'Student compression failed. The previous ZIP was kept if validation failed.' }
