@echo off
REM ==========================================================================
REM  Setup script for Annotator XE (Windows / cmd.exe)
REM
REM  Creates an isolated Python virtual environment and installs the project.
REM
REM  Usage:
REM    scripts\setup.bat [options]
REM
REM  Options:
REM    --dev        Also install development tools (pytest, ruff, black, mypy)
REM    --yolo       Also install auto-detection deps (torch, ultralytics) [heavy]
REM    --gpu        Also install GPU/OpenGL rendering deps (PyOpenGL)
REM    --all        Install everything (--dev --yolo --gpu)
REM    --recreate   Delete and rebuild the virtual environment from scratch
REM    -h, --help   Show this help and exit
REM
REM  Note: for a richer experience use the PowerShell version: scripts\setup.ps1
REM ==========================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENV_DIR=%PROJECT_DIR%\venv"

set WANT_DEV=0
set WANT_YOLO=0
set WANT_GPU=0
set RECREATE=0

REM ---- Parse arguments ----------------------------------------------------
:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--dev"      ( set WANT_DEV=1 )
if /i "%~1"=="--yolo"     ( set WANT_YOLO=1 )
if /i "%~1"=="--gpu"      ( set WANT_GPU=1 )
if /i "%~1"=="--all"      ( set WANT_DEV=1& set WANT_YOLO=1& set WANT_GPU=1 )
if /i "%~1"=="--recreate" ( set RECREATE=1 )
if /i "%~1"=="-h"         ( goto help )
if /i "%~1"=="--help"     ( goto help )
shift
goto parse
:parsed

echo ========================================
echo   Annotator XE - Setup (Windows)
echo ========================================
echo.

REM ---- Locate Python ------------------------------------------------------
set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        python -c "import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul
        if !errorlevel! equ 0 set "PYTHON_CMD=python"
    )
)
if not defined PYTHON_CMD (
    echo [ERROR] No Python ^>= 3.10 found.
    echo Install from https://www.python.org/downloads/ and tick "Add to PATH".
    exit /b 1
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% -c "import sys;print(\"%%d.%%d.%%d\"%%sys.version_info[:3])"') do set "PYVER=%%i"
echo [OK] Using Python %PYVER% (%PYTHON_CMD%)

REM ---- Virtual environment ------------------------------------------------
if "%RECREATE%"=="1" if exist "%VENV_DIR%" (
    echo ==^> Removing existing virtual environment ^(--recreate^)...
    rmdir /s /q "%VENV_DIR%"
)

if not exist "%VENV_DIR%" (
    echo ==^> Creating virtual environment at %VENV_DIR% ...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 ( echo [ERROR] Failed to create venv.& exit /b 1 )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Reusing existing virtual environment.
)

set "VPY=%VENV_DIR%\Scripts\python.exe"
if not exist "%VPY%" (
    echo [ERROR] venv interpreter missing. Try: scripts\setup.bat --recreate
    exit /b 1
)

REM ---- Install ------------------------------------------------------------
echo ==^> Upgrading pip / setuptools / wheel ...
"%VPY%" -m pip install --upgrade pip setuptools wheel >nul
if %errorlevel% neq 0 ( echo [ERROR] pip upgrade failed.& exit /b 1 )

set "EXTRAS="
if "%WANT_DEV%"=="1"  ( if defined EXTRAS (set "EXTRAS=!EXTRAS!,dev")  else (set "EXTRAS=dev") )
if "%WANT_YOLO%"=="1" ( if defined EXTRAS (set "EXTRAS=!EXTRAS!,yolo") else (set "EXTRAS=yolo") )

set "SPEC=."
if defined EXTRAS set "SPEC=.[!EXTRAS!]"

echo ==^> Installing Annotator XE ^(editable^) -^> !SPEC!
pushd "%PROJECT_DIR%"
"%VPY%" -m pip install -e "!SPEC!"
set "RC=!errorlevel!"
popd
if %RC% neq 0 ( echo [ERROR] Install failed.& exit /b 1 )

if "%WANT_GPU%"=="1" (
    echo ==^> Installing GPU/OpenGL rendering deps ^(PyOpenGL^) ...
    "%VPY%" -m pip install "PyOpenGL>=3.1.6"
)

REM ---- Sanity check -------------------------------------------------------
echo ==^> Verifying PyQt6 import ...
"%VPY%" -c "import PyQt6.QtWidgets" >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] PyQt6 imports cleanly.
) else (
    echo [WARN] PyQt6 installed but failed to import. The app may not launch.
    echo        Reinstall PyQt6 or check your Windows runtime libraries.
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Start the app:
echo   scripts\start.bat
echo.
echo Or manually:
echo   venv\Scripts\activate.bat
echo   annotator-xe
echo.
if "%WANT_YOLO%"=="0" echo Auto-detection (YOLO) not installed. Add later: scripts\setup.bat --yolo
if "%WANT_GPU%"=="0"  echo GPU/OpenGL rendering not installed. Add later:  scripts\setup.bat --gpu
echo.

endlocal
exit /b 0

:help
echo Usage: scripts\setup.bat [--dev] [--yolo] [--gpu] [--all] [--recreate]
echo   --dev       development tools (pytest, ruff, black, mypy)
echo   --yolo      auto-detection deps (torch, ultralytics) [heavy ~2GB+]
echo   --gpu       GPU/OpenGL rendering deps (PyOpenGL)
echo   --all       everything
echo   --recreate  rebuild the virtual environment from scratch
endlocal
exit /b 0
