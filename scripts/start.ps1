<#
.SYNOPSIS
    Start script for Annotator XE (Windows PowerShell / PowerShell Core).

.DESCRIPTION
    Launches the application from the project's virtual environment.
    Runs setup automatically if the venv does not yet exist.
    Any extra arguments are passed straight through to the app.

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 --some-app-flag
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$VenvDir    = Join-Path $ProjectDir 'venv'
$Vpy        = Join-Path $VenvDir 'Scripts\python.exe'

# Bootstrap the environment on first run.
if (-not (Test-Path $Vpy)) {
    Write-Host "Virtual environment not found - running setup first..."
    & (Join-Path $ScriptDir 'setup.ps1')
}

if (-not (Test-Path $Vpy)) {
    Write-Error "Setup did not produce a usable environment. Aborting."
    exit 1
}

Write-Host "Starting Annotator XE..."
Push-Location $ProjectDir
try {
    & $Vpy -m annotator_xe @AppArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
