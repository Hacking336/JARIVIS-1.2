@echo off
REM JARVIS Startup Script for Windows
REM ================================

echo ========================================
echo   J.A.R.V.I.S. - Personal AI Control Center
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

REM Create data directory if not exists
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "voice_cache" mkdir voice_cache

REM Check for .env file
if not exist ".env" (
    echo.
    echo WARNING: No .env file found. Creating from template...
    copy .env.example .env
    echo Please edit .env with your configuration before starting.
    echo.
)

REM Initialize database
echo Initializing database...
python -c "from app.storage.database import init_database; init_database()"

REM Start JARVIS
echo.
echo Starting JARVIS on http://127.0.0.1:3000
echo Press Ctrl+C to stop
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 3000 --reload

REM Cleanup
call venv\Scripts\deactivate.bat

pause
