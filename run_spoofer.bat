@echo off
:: SP5-CUBE MitM Gateway Launcher
:: This script sets the PYTHONPATH and launches the application via the virtual environment.

set "PROJECT_ROOT=%~dp0"
set "PYTHONPATH=%PROJECT_ROOT%"

echo Starting SP5-CUBE MitM Gateway...
"%PROJECT_ROOT%.venv\Scripts\python.exe" "%PROJECT_ROOT%src\main.py"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application crashed with exit code %ERRORLEVEL%
    pause
)
