@echo off
setlocal
title English Intensive Reading System - 127.0.0.1:8001
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found:
    echo         %~dp0.venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py"

echo.
echo Service stopped.
pause
endlocal
