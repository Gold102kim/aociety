@echo off
setlocal
chcp 65001 >nul
title Aociety Full Stack Launcher

cd /d "%~dp0"

if exist .env (
    echo [INFO] Loading local .env...
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
)

if "%AOCIETY_PORT%"=="" set "AOCIETY_PORT=8000"
if "%HARDWARE_CARE_PORT%"=="" set "HARDWARE_CARE_PORT=8010"

echo =============================================
echo   Aociety Full Stack
echo   Residents: DeepSeek V4 Flash
echo   Proactive care: hardware-side service
echo =============================================
echo.

echo [1/3] Starting forest resident service on %AOCIETY_PORT%...
start "Aociety-Residents" cmd /c "python -m uvicorn services.app:app --host 127.0.0.1 --port %AOCIETY_PORT% --log-level info"

echo [2/3] Starting hardware care backend on %HARDWARE_CARE_PORT%...
start "Aociety-HardwareCare" cmd /c "python -m uvicorn backend.main:app --host 127.0.0.1 --port %HARDWARE_CARE_PORT% --log-level info"

echo Waiting for resident service...
:wait_residents
timeout /t 1 /nobreak >nul
curl.exe -sf "http://127.0.0.1:%AOCIETY_PORT%/health" >nul 2>&1
if errorlevel 1 goto wait_residents

echo Waiting for hardware care backend...
:wait_hardware
timeout /t 1 /nobreak >nul
curl.exe -sf "http://127.0.0.1:%HARDWARE_CARE_PORT%/health" >nul 2>&1
if errorlevel 1 goto wait_hardware

echo [3/3] Starting camera, microphone, ASR and pose pipeline...
start "Aociety-HardwarePipeline" cmd /c "python -m services.emotion_pipeline --backend http://127.0.0.1:%HARDWARE_CARE_PORT%"

echo.
echo All services are ready.
echo Resident health: http://127.0.0.1:%AOCIETY_PORT%/health
echo Resident probe:  POST http://127.0.0.1:%AOCIETY_PORT%/forest/probe
echo Hardware care:   http://127.0.0.1:%HARDWARE_CARE_PORT%/health
echo.
echo Press any key to stop all Aociety services...
pause >nul

taskkill /fi "WINDOWTITLE eq Aociety-Residents" /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq Aociety-HardwareCare" /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq Aociety-HardwarePipeline" /t /f >nul 2>&1
endlocal
