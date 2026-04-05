@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Starting College Voice Agent (Local Mode)
echo ========================================
echo.

REM Check if local.env exists
if not exist "%~dp0local.env" (
    echo ERROR: local.env not found!
    echo Please create local.env from local.env.example
    echo.
    echo Press any key to open local.env.example...
    pause >nul
    start notepad "%~dp0local.env.example"
    exit /b 1
)

REM Load environment variables from local.env
echo Loading configuration from local.env...
for /f "usebackq tokens=1,2 delims==" %%a in ("%~dp0local.env") do (
    set "line=%%a"
    REM Skip comments and empty lines
    echo !line! | findstr /b "#" >nul
    if errorlevel 1 (
        echo !line! | findstr /r "^$" >nul
        if errorlevel 1 (
            set "%%a=%%b"
        )
    )
)

REM ============================================
REM OLLAMA CHECK - Required for Local LLM
REM ============================================
echo.
echo Checking Ollama...

REM Check if Ollama is already running
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Ollama is already running
    goto :check_deps
)

REM Try to start Ollama
echo   [INFO] Ollama not running, attempting to start...
start /min "" ollama serve
timeout /t 3 /nobreak > nul

REM Check again
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Ollama started successfully
    goto :check_deps
)

echo.
echo ========================================
echo WARNING: Ollama is not running!
echo ========================================
echo The system needs Ollama for local LLM processing.
echo.
echo Please start Ollama manually:
echo   - Open a new terminal
echo   - Run: ollama serve
echo   - Then run this script again
echo.
echo OR press Ctrl+C to exit and start Ollama first.
echo.
pause

:check_deps

REM Check if backend dependencies are installed
echo.
echo Checking backend dependencies...
pip show rank-bm25 >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing missing backend dependencies...
    pip install -r "%~dp0backend\requirements.txt"
)

REM Check for faster-whisper (optional but recommended)
pip show faster-whisper >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] faster-whisper installed (Local STT)
) else (
    echo   [OPTIONAL] faster-whisper not installed
    echo   Install with: pip install faster-whisper
)

echo.
echo ========================================
echo Configuration Loaded:
echo   College: %COLLEGE_NAME%
echo   Phone: %ADMISSIONS_PHONE%
echo   LLM Mode: Local (Ollama)
if not "%GROQ_API_KEY%"=="" (
    echo   Groq: Available (fallback mode)
) else (
    echo   Groq: Not configured
)
echo ========================================
echo.

REM Start Backend
echo Starting Backend Server...
set "BACKEND_CMD=cd /d %~dp0backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
if not "%GROQ_API_KEY%"=="" (
    start "Backend Server" cmd /k "set GROQ_API_KEY=%GROQ_API_KEY% && !BACKEND_CMD!"
) else (
    start "Backend Server" cmd /k "!BACKEND_CMD!"
)

timeout /t 5 /nobreak > nul

REM Start Frontend
echo.
echo Starting Frontend Server...
start "Frontend Server" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 5 /nobreak > nul

echo.
echo ========================================
echo Servers Starting!
echo ========================================
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Opening browser in 5 seconds...
timeout /t 5 /nobreak > nul

start http://localhost:5173

echo.
echo ========================================
echo All systems running!
echo ========================================
echo.
echo [Local Mode Active]
echo - LLM: Using Ollama (qwen3.5 or mistral)
echo - STT: Browser Web Speech API (or faster-whisper if installed)
echo - TTS: Piper/gTTS (local)
echo.
echo To stop the servers, close the terminal windows.
echo.

endlocal
