@echo off
REM Run script for Annotator XE (Windows)
REM Kept as a backwards-compatible alias for start.bat.
call "%~dp0start.bat" %*
exit /b %errorlevel%
