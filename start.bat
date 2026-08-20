@echo off
chcp 936 >nul 2>&1
title Wheat Fe Experiment System

cd /d "%~dp0"

echo ============================================
echo   Wheat Fe Experiment System
echo ============================================
echo.

rem ---- Step 1: Clear port ----
echo [1/3] Checking port 8001...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo   Found process on port 8001, killing PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)
echo   Port check done.
echo.

rem ---- Step 2: Check Python ----
echo [2/3] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found!
    echo   Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Found: %%v
echo   Python OK.
echo.

rem ---- Step 3: Check dependencies ----
echo [3/3] Checking dependencies...
python -c "import uvicorn, fastapi, pandas, psycopg2; print('  Dependencies OK')"
if errorlevel 1 (
    echo   Installing dependencies...
    python -m pip install uvicorn fastapi pandas psycopg2-binary qrcode[pil] pyyaml
    if errorlevel 1 (
        echo   [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
)
echo.

rem ---- Open browser after 5 seconds (background) ----
echo Opening browser in 5 seconds...
start "" /b cmd /c "timeout /t 5 /nobreak >nul && start http://localhost:8001/"

echo ============================================
echo   Starting server...
echo   UI (this PC): http://localhost:8001
echo   API:         http://localhost:8001/api/v1/
echo   Docs:        http://localhost:8001/docs
echo   Mobile:      Scan QR code on the website
echo   Mobile PW:   wheat123 (configurable via MOBILE_PASSWORD env)
echo   Press Ctrl+C to stop
echo ============================================
echo.

rem ---- Start backend (foreground, keeps window open) ----
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8001

echo.
echo Server stopped.
pause
