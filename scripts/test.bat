@echo off
REM Test script for Annotator XE (Windows)

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENV_DIR=%PROJECT_DIR%\venv"

REM Check if virtual environment exists
if not exist "%VENV_DIR%" (
    echo Virtual environment not found. Running setup first...
    call "%SCRIPT_DIR%\setup.bat" --dev
)

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Ensure dev dependencies are installed
pip install -e ".[dev]" --quiet

cd "%PROJECT_DIR%"

echo ========================================
echo   Running Tests
echo ========================================
echo.

if "%1"=="--coverage" (
    pytest --cov=annotator_xe --cov-report=html --cov-report=term
    echo.
    echo Coverage report generated in htmlcov/
) else if "%1"=="--verbose" (
    pytest -v --tb=long
) else (
    pytest
)

endlocal
