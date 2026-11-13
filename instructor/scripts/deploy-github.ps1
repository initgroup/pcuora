param(
    [string]$Repository = 'https://github.com/initgroup/pcuora.git',
    [string]$Branch = 'main',
    [string]$Message = 'Update OML classroom source',
    [string]$AuthorName = '',
    [string]$AuthorEmail = '',
    [switch]$Prepare,
    [switch]$Push
)
. (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'scripts/common.ps1')
Require-Python
if ($Prepare -and $Push) { throw 'Choose -Prepare or -Push, not both.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first.' }
$arguments = @((Join-Path $PSScriptRoot 'git_publish.py'), '--repository', $Repository, '--branch', $Branch, '--message', $Message)
if ($AuthorName) { $arguments += @('--author-name', $AuthorName) }
if ($AuthorEmail) { $arguments += @('--author-email', $AuthorEmail) }
if ($Prepare) { $arguments += '--prepare' }
if ($Push) { $arguments += '--push' }
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Git publication stopped. Review the error above; no force push is used.' }
