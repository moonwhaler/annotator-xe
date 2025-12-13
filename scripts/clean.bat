@echo off
REM Clean script for Annotator XE (Windows)
REM Removes build artifacts and cache files

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

cd "%PROJECT_DIR%"

echo ========================================
echo   Cleaning Annotator XE
echo ========================================

echo.
echo Removing build artifacts...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
for /d %%i in (*.egg-info) do rmdir /s /q "%%i" 2>nul
for /d %%i in (src\*.egg-info) do rmdir /s /q "%%i" 2>nul

echo Removing Python cache...
for /d /r %%i in (__pycache__) do rmdir /s /q "%%i" 2>nul
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul

echo Removing test artifacts...
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist htmlcov rmdir /s /q htmlcov
if exist .coverage del /q .coverage
if exist .mypy_cache rmdir /s /q .mypy_cache

if "%1"=="--all" (
    echo.
    echo Removing virtual environment...
    if exist venv rmdir /s /q venv
)

echo.
echo ========================================
echo   Clean Complete!
echo ========================================

if "%1"=="--all" (
    echo.
    echo Virtual environment removed. Run setup.bat to reinstall.
)

endlocal
