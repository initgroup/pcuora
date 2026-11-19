[CmdletBinding(DefaultParameterSetName='Publish')]
param(
    [Parameter(ParameterSetName='Publish')][switch]$Push,
    [Parameter(ParameterSetName='Preview')][switch]$Preview,
    [Parameter(ParameterSetName='Prepare')][switch]$Prepare,
    [string]$Message = 'Redeploy complete OML classroom source',
    [string]$AuthorName = '',
    [string]$AuthorEmail = ''
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$publisher = Join-Path $ProjectRoot 'instructor/scripts/deploy-github.ps1'
if (-not (Test-Path -LiteralPath $publisher -PathType Leaf)) {
    throw 'This is the instructor OML source entry point. instructor/scripts/deploy-github.ps1 is required.'
}
$publishOptions = @{ Branch = 'main'; Message = $Message; Republish = $true }
if ($AuthorName) { $publishOptions.AuthorName = $AuthorName }
if ($AuthorEmail) { $publishOptions.AuthorEmail = $AuthorEmail }
if ($Prepare) {
    $publishOptions.Prepare = $true
} elseif (-not $Preview) {
    $publishOptions.Push = $true
}
& $publisher @publishOptions
