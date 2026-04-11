@echo off
title BCREC Voice Agent - Starting...

echo.
echo ========================================
echo    BCREC Voice Agent - Starting
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Checking Python requirements...
cd /d "%~dp0backend"
python -m pip install --quiet -r requirements.txt 2>nul
if errorlevel 1 (
    echo WARNING: Some packages may not be installed. Run: pip install -r requirements.txt
)

echo [2/5] Starting Backend Server on port 8000...
start "Backend Server" cmd /k "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo [3/5] Waiting for backend to start...
timeout /t 8 /nobreak > nul

echo [4/5] Starting Frontend Server on port 5173...
cd /d "%~dp0frontend"
start "Frontend Server" cmd /k "npm run dev"

echo [5/5] Opening browser...
timeout /t 3 /nobreak > nul
start http://localhost:5173

echo.
echo ========================================
echo    All servers started!
echo ========================================
echo.
echo Backend API:   http://localhost:8000
echo Frontend UI:   http://localhost:5173
echo.
echo Press any key to exit this window...
pause >nul
