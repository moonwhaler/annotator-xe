@echo off
REM Lint script for Annotator XE (Windows)

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
echo   Code Quality Checks
echo ========================================

if "%1"=="--fix" (
    echo.
    echo Running Ruff (with auto-fix)...
    ruff check src/annotator_xe --fix

    echo.
    echo Running Black (formatting)...
    black src/annotator_xe
) else (
    echo.
    echo Running Ruff...
    ruff check src/annotator_xe

    echo.
    echo Running Black (check only)...
    black --check src/annotator_xe
)

echo.
echo Running MyPy...
mypy src/annotator_xe

echo.
echo ========================================
echo   Done!
echo ========================================

endlocal
