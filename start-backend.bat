@echo off
echo ========================================
echo Starting College Voice Agent Backend
echo ========================================
echo.

cd /d "%~dp0backend"

echo Starting backend server...
echo Backend will be available at: http://localhost:8000
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
