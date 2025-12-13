@echo off
REM Setup script for Annotator XE (Windows)
REM Creates virtual environment and installs dependencies

setlocal enabledelayedexpansion

echo ========================================
echo   Annotator XE - Setup
echo ========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENV_DIR=%PROJECT_DIR%\venv"

REM Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.10 or higher.
    exit /b 1
)

REM Check Python version
for /f "tokens=*" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

for /f "tokens=*" %%i in ('python -c "import sys; print(sys.version_info.major)"') do set MAJOR=%%i
for /f "tokens=*" %%i in ('python -c "import sys; print(sys.version_info.minor)"') do set MINOR=%%i

if %MAJOR% lss 3 (
    echo Error: Python 3.10 or higher is required
    exit /b 1
)
if %MAJOR% equ 3 if %MINOR% lss 10 (
    echo Error: Python 3.10 or higher is required
    exit /b 1
)

REM Create virtual environment
if not exist "%VENV_DIR%" (
    echo.
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    echo Virtual environment created at: %VENV_DIR%
) else (
    echo.
    echo Virtual environment already exists at: %VENV_DIR%
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
echo.
echo Upgrading pip...
pip install --upgrade pip

REM Install package
echo.
echo Installing Annotator XE...
cd "%PROJECT_DIR%"

if "%1"=="--dev" (
    echo (Development mode with testing tools)
    pip install -e ".[dev]"
) else (
    pip install -e .
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo To activate the virtual environment:
echo   venv\Scripts\activate.bat
echo.
echo To run Annotator XE:
echo   annotator-xe
echo   or: scripts\run.bat
echo.

endlocal
