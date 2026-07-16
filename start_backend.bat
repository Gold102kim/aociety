@echo off
chcp 65001 >nul
echo =============================================
echo   Aociety - 统一后端启动脚本
echo =============================================
echo.

cd /d %~dp0

if "%BIGMODEL_API_KEY%"=="" (
    if exist .env (
        echo [INFO] 从 .env 加载环境变量...
        for /f "tokens=*" %%a in (.env) do set %%a
    )
)

echo [1/2] 启动主后端服务 (端口 %AOCIETY_PORT%)
start "Aociety-Backend" cmd /c "uvicorn backend.main:app --host 0.0.0.0 --port %AOCIETY_PORT% --reload --log-level info"

echo [2/2] 等待服务就绪...
timeout /t 3 /nobreak >nul

echo.
echo =============================================
echo   服务已启动!
echo   主后端: http://127.0.0.1:%AOCIETY_PORT%
echo   API文档: docs/API_UE5.md
echo =============================================
echo.
echo 按任意键停止服务...
pause >nul

echo 正在停止服务...
taskkill /fi "WINDOWTITLE eq Aociety-Backend" /f >nul 2>&1
echo 已停止。
