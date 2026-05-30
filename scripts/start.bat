@echo off
REM ==========================================================================
REM  Start script for Annotator XE (Windows / cmd.exe)
REM
REM  Launches the application from the project's virtual environment.
REM  Runs setup automatically if the venv does not yet exist.
REM  Any extra arguments are passed straight through to the app.
REM
REM  Usage:
REM    scripts\start.bat [app arguments...]
REM ==========================================================================

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENV_DIR=%PROJECT_DIR%\venv"
set "VPY=%VENV_DIR%\Scripts\python.exe"

REM Bootstrap the environment on first run.
if not exist "%VPY%" (
    echo Virtual environment not found - running setup first...
    call "%SCRIPT_DIR%setup.bat"
)

if not exist "%VPY%" (
    echo Setup did not produce a usable environment. Aborting.
    exit /b 1
)

echo Starting Annotator XE...
pushd "%PROJECT_DIR%"
"%VPY%" -m annotator_xe %*
set "RC=%errorlevel%"
popd

endlocal & exit /b %RC%
