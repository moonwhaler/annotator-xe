@echo off
REM Build script for Annotator XE (Windows)
REM Creates distributable package

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

cd "%PROJECT_DIR%"

echo ========================================
echo   Building Annotator XE
echo ========================================

REM Install build tools
echo.
echo Installing build tools...
pip install --upgrade build twine

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"
for /d %%i in (src\*.egg-info) do rmdir /s /q "%%i"

REM Build package
echo.
echo Building package...
python -m build

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Distribution files created in dist/
dir dist
echo.
echo To install locally:
echo   pip install dist\annotator_xe-*.whl
echo.
echo To upload to PyPI (requires credentials):
echo   twine upload dist\*
echo.

endlocal
