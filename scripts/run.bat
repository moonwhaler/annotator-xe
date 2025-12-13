@echo off
REM Run script for Annotator XE (Windows)

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENV_DIR=%PROJECT_DIR%\venv"

REM Check if virtual environment exists
if not exist "%VENV_DIR%" (
    echo Virtual environment not found. Running setup first...
    call "%SCRIPT_DIR%\setup.bat"
)

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Run the application
echo Starting Annotator XE...
cd "%PROJECT_DIR%"

if "%1"=="--legacy" (
    python pyQT_YOLO.py
) else (
    python -m annotator_xe
)

endlocal
