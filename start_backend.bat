@echo off
setlocal
chcp 65001 >nul
title Aociety Resident Service Launcher

cd /d "%~dp0"

if exist .env (
    echo [INFO] Loading local .env...
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
)

if "%AOCIETY_PORT%"=="" set "AOCIETY_PORT=8000"

echo =============================================
echo   Aociety Forest Resident Service
echo   DeepSeek V4 Flash - port %AOCIETY_PORT%
echo =============================================

start "Aociety-Residents" cmd /c "python -m uvicorn services.app:app --host 127.0.0.1 --port %AOCIETY_PORT% --log-level info"

echo Waiting for http://127.0.0.1:%AOCIETY_PORT%/health ...
:wait_residents
timeout /t 1 /nobreak >nul
curl.exe -sf "http://127.0.0.1:%AOCIETY_PORT%/health" >nul 2>&1
if errorlevel 1 goto wait_residents

echo.
echo Resident service is ready.
echo Health: http://127.0.0.1:%AOCIETY_PORT%/health
echo Probe:  POST http://127.0.0.1:%AOCIETY_PORT%/forest/probe
echo.
echo Press any key to stop the resident service...
pause >nul

taskkill /fi "WINDOWTITLE eq Aociety-Residents" /t /f >nul 2>&1
endlocal
