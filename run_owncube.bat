@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PYTHONPATH=%PROJECT_ROOT%"
set "RUNTIME_ROOT=%LOCALAPPDATA%\RS232-spoofer"
set "VENV_DIR=%RUNTIME_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%RUNTIME_ROOT%" mkdir "%RUNTIME_ROOT%" >nul 2>&1

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo Detected an invalid virtual environment. Rebuilding it...
        rmdir /s /q "%VENV_DIR%" >nul 2>&1
    )
)

if not exist "%VENV_PYTHON%" (
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

"%VENV_PYTHON%" -c "import PyQt6, serial" >nul 2>&1
if errorlevel 1 (
    echo Installing Python dependencies...
    "%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%requirements.txt"
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies from requirements.txt
        pause
        exit /b 1
    )
)

echo Starting ownCUBE...
"%VENV_PYTHON%" "%PROJECT_ROOT%src\owncube_main.py"
set "APP_EXIT=%ERRORLEVEL%"

if %APP_EXIT% neq 0 (
    echo.
    echo [ERROR] Application crashed with exit code %APP_EXIT%
    pause
)

exit /b %APP_EXIT%
