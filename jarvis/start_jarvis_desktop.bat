@echo off
REM JARVIS Desktop Launcher - Native Windows Application
REM =====================================================

echo ========================================
echo   J.A.R.V.I.S. - Personal AI Control Center
echo   Native Desktop Edition
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check for virtual environment
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM Verify PySide6 with WebEngine
python -c "from PySide6.QtWebEngineWidgets import QWebEngineView; print('Qt WebEngine: OK')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: PySide6 with Qt WebEngine not available.
    echo Please install: pip install PySide6
    pause
    exit /b 1
)

REM Create data directories
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "voice_cache" mkdir voice_cache
if not exist "webengine_cache" mkdir webengine_cache

REM Check for .env file
if not exist ".env" (
    echo.
    echo WARNING: No .env file found. Creating from template...
    copy .env.example .env
    echo Please edit .env with your configuration before starting.
    echo.
)

REM Check for llama.cpp server executable
if not exist "llama-server.exe" (
    echo WARNING: llama-server.exe not found in project root.
    echo Local AI inference may not work.
    echo.
)

REM Check for GGUF model
if not exist "Qwen3-1.7B-Q4_K_M.gguf" (
    echo WARNING: Qwen3-1.7B-Q4_K_M.gguf not found in project root.
    echo Local AI inference may not work.
    echo.
)

REM Initialize database
echo Initializing database...
python -c "from app.storage.database import init_database; init_database()" 2>nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: Database initialization failed (may already exist).
)

REM Launch JARVIS Desktop Application
echo.
echo Starting JARVIS Desktop Application...
echo.

python desktop_main.py

REM Cleanup
call venv\Scripts\deactivate.bat

echo.
echo JARVIS has been shut down.
pause
