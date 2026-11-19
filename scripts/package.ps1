[CmdletBinding()]
param([string]$StudentId='', [string]$Output='')
# Legacy command name; compress.ps1 is the single packaging entry point.
& "$PSScriptRoot/compress.ps1" -StudentId $StudentId -Output $Output
