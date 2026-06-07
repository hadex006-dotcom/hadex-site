@echo off
title Hadex Factory - Local Server
echo ============================================
echo  Starting Hadex Factory website locally...
echo ============================================
echo.
cd /d "%~dp0"

REM Install dependencies if needed
python -m pip install -r requirements.txt >nul 2>&1

REM Set a local admin password (CHANGE THIS!)
set ADMIN_PASSWORD=hadex123
set SECRET_KEY=local-dev-key

echo Open your browser to:  http://localhost:5000
echo Admin/upload page:     http://localhost:5000/admin   (password: hadex123)
echo.
echo Press CTRL+C to stop the server.
echo.
python app.py
pause
