<#
.SYNOPSIS
    Setup script for Annotator XE (Windows PowerShell / PowerShell Core).

.DESCRIPTION
    Creates an isolated Python virtual environment and installs the project
    in editable mode, with optional feature extras.

.PARAMETER Dev
    Also install development tools (pytest, ruff, black, mypy, ...).

.PARAMETER Yolo
    Also install auto-detection deps (torch, ultralytics). Heavy (~2GB+).

.PARAMETER Gpu
    Also install GPU/OpenGL rendering deps (PyOpenGL).

.PARAMETER All
    Install everything (-Dev -Yolo -Gpu).

.PARAMETER Recreate
    Delete and rebuild the virtual environment from scratch.

.PARAMETER Python
    Path to a specific Python interpreter to use.

.EXAMPLE
    .\scripts\setup.ps1
    .\scripts\setup.ps1 -All
    .\scripts\setup.ps1 -Dev -Recreate
#>
[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Yolo,
    [switch]$Gpu,
    [switch]$All,
    [switch]$Recreate,
    [string]$Python
)

$ErrorActionPreference = 'Stop'

if ($All) { $Dev = $true; $Yolo = $true; $Gpu = $true }

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$VenvDir    = Join-Path $ProjectDir 'venv'

function Write-Step($m) { Write-Host "==> $m" -ForegroundColor Blue }
function Write-Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Warn2($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Header($m) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor White
    Write-Host "  $m" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor White
    Write-Host ""
}

Write-Header "Annotator XE - Setup (Windows / PowerShell)"

# ---- Locate Python (>= 3.10) -------------------------------------------
function Test-PyVersion($exe) {
    try {
        & $exe -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

$PythonCmd = $null
if ($Python) {
    if (Test-PyVersion $Python) { $PythonCmd = $Python }
    else { throw "Provided interpreter '$Python' missing or older than 3.10." }
} else {
    # Prefer the 'py' launcher, then bare python.
    foreach ($cand in @('py', 'python', 'python3')) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            $probe = if ($cand -eq 'py') { 'py -3' } else { $cand }
            if (Test-PyVersion $probe) { $PythonCmd = $probe; break }
        }
    }
}

if (-not $PythonCmd) {
    Write-Warn2 "No Python >= 3.10 found."
    Write-Warn2 "Install from https://www.python.org/downloads/ and tick 'Add to PATH'."
    exit 1
}

$pyver = & ($PythonCmd -split ' ')[0] ($PythonCmd -split ' ' | Select-Object -Skip 1) -c "import sys;print('%d.%d.%d'%sys.version_info[:3])"
Write-Ok "Using Python $pyver ($PythonCmd)"

# ---- Virtual environment ----------------------------------------------
if ($Recreate -and (Test-Path $VenvDir)) {
    Write-Step "Removing existing virtual environment (-Recreate)..."
    Remove-Item -Recurse -Force $VenvDir
}

if (-not (Test-Path $VenvDir)) {
    Write-Step "Creating virtual environment at $VenvDir ..."
    & ($PythonCmd -split ' ')[0] ($PythonCmd -split ' ' | Select-Object -Skip 1) -m venv $VenvDir
    Write-Ok "Virtual environment created."
} else {
    Write-Ok "Reusing existing virtual environment."
}

$Vpy = Join-Path $VenvDir 'Scripts\python.exe'
if (-not (Test-Path $Vpy)) {
    throw "venv interpreter missing at $Vpy. Try: .\scripts\setup.ps1 -Recreate"
}

# ---- Install -----------------------------------------------------------
Write-Step "Upgrading pip / setuptools / wheel ..."
& $Vpy -m pip install --upgrade pip setuptools wheel | Out-Null

$extras = @()
if ($Dev)  { $extras += 'dev' }
if ($Yolo) { $extras += 'yolo' }
$spec = if ($extras.Count -gt 0) { ".[$($extras -join ',')]" } else { "." }

Write-Step "Installing Annotator XE (editable) -> $spec"
Push-Location $ProjectDir
try {
    & $Vpy -m pip install -e $spec
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
} finally {
    Pop-Location
}

if ($Gpu) {
    Write-Step "Installing GPU/OpenGL rendering deps (PyOpenGL) ..."
    & $Vpy -m pip install "PyOpenGL>=3.1.6"
}

# ---- Sanity check ------------------------------------------------------
Write-Step "Verifying PyQt6 import ..."
& $Vpy -c "import PyQt6.QtWidgets" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "PyQt6 imports cleanly."
} else {
    Write-Warn2 "PyQt6 installed but failed to import. The app may not launch."
}

Write-Header "Setup Complete!"
Write-Host "Start the app:"
Write-Host "  .\scripts\start.ps1"
Write-Host ""
Write-Host "Or manually:"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  annotator-xe"
Write-Host ""
if (-not $Yolo) { Write-Host "Auto-detection (YOLO) not installed. Add later: .\scripts\setup.ps1 -Yolo" }
if (-not $Gpu)  { Write-Host "GPU/OpenGL rendering not installed. Add later:  .\scripts\setup.ps1 -Gpu" }
Write-Host ""
