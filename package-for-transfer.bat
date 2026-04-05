@echo off
echo ========================================
echo Packaging Project for Transfer
echo ========================================
echo.

REM Create a clean package directory
set PACKAGE_DIR=college-agent-clean
set SOURCE_DIR=.

echo Creating clean package directory...
if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
mkdir "%PACKAGE_DIR%"

echo.
echo Copying essential files...
echo.

REM Copy backend using robocopy (more reliable)
echo [1/4] Copying backend...
robocopy "%SOURCE_DIR%\backend" "%PACKAGE_DIR%\backend" /E /XD __pycache__ uploads chroma_db /NFL /NDL /NJH /NJS >nul 2>&1

REM Copy frontend using robocopy (excludes node_modules)
echo [2/4] Copying frontend...
robocopy "%SOURCE_DIR%\frontend" "%PACKAGE_DIR%\frontend" /E /XD node_modules .vite dist /NFL /NDL /NJH /NJS >nul 2>&1

REM Copy root files
echo [3/4] Copying root files...
copy "%SOURCE_DIR%\*.md" "%PACKAGE_DIR%\" >nul 2>&1
copy "%SOURCE_DIR%\*.bat" "%PACKAGE_DIR%\" >nul 2>&1
copy "%SOURCE_DIR%\*.yml" "%PACKAGE_DIR%\" >nul 2>&1
copy "%SOURCE_DIR%\*.yaml" "%PACKAGE_DIR%\" >nul 2>&1
copy "%SOURCE_DIR%\.gitignore" "%PACKAGE_DIR%\" >nul 2>&1

REM Create README for package
echo [4/4] Creating setup instructions...
(
echo # College Voice Agent - Clean Package
echo.
echo This is a clean package without node_modules and cache files.
echo.
echo ## Setup Instructions:
echo.
echo ### Backend:
echo 1. cd backend
echo 2. pip install -r requirements.txt
echo 3. python -m uvicorn app.main:app --reload
echo.
echo ### Frontend:
echo 1. cd frontend
echo 2. npm install
echo 3. npm run dev
echo.
echo ### Configuration:
echo - Add your API keys to backend/.env file
echo - See README.md for full setup instructions
) > "%PACKAGE_DIR%\SETUP.txt"

echo.
echo ========================================
echo Package Created Successfully!
echo ========================================
echo.
echo Package location: %PACKAGE_DIR%
echo.
echo Next steps:
echo 1. Zip the "%PACKAGE_DIR%" folder
echo 2. Transfer the zip file
echo 3. On destination, unzip and run:
echo    - Frontend: cd frontend ^&^& npm install
echo    - Backend: cd backend ^&^& pip install -r requirements.txt
echo.
echo Press any key to open the package folder...
pause >nul
explorer "%PACKAGE_DIR%"

