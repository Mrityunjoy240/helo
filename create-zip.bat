@echo off
echo ========================================
echo Creating ZIP Package
echo ========================================
echo.

REM First run the package script
call package-for-transfer.bat

echo.
echo Creating ZIP file...
echo.

REM Create ZIP using PowerShell
powershell -Command "Compress-Archive -Path 'college-agent-clean\*' -DestinationPath 'college-agent-transfer.zip' -Force"

if exist "college-agent-transfer.zip" (
    echo.
    echo ========================================
    echo ZIP Created Successfully!
    echo ========================================
    echo.
    echo File: college-agent-transfer.zip
    echo.
    powershell -Command "$size = (Get-Item 'college-agent-transfer.zip').Length / 1MB; Write-Host ('Size: ' + [math]::Round($size, 2).ToString() + ' MB')"
    echo.
    echo You can now transfer this ZIP file!
    echo.
) else (
    echo.
    echo Error: Failed to create ZIP file
    echo.
)

pause

