@echo off
echo ========================================
echo College Voice Agent - Quick Setup
echo ========================================
echo.

echo Step 1: Installing Frontend Dependencies...
cd frontend
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed!
    echo Please make sure Node.js is installed: https://nodejs.org/
    pause
    exit /b 1
)
cd ..

echo.
echo Step 2: Installing Backend Dependencies...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed!
    echo Please make sure Python 3.11+ is installed
    pause
    exit /b 1
)
cd ..

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Install OLLAMA from: https://ollama.ai/
echo 2. Run: ollama serve
echo 3. Run: ollama pull llama3.2:3b
echo 4. Run: start-app.bat
echo.
pause
