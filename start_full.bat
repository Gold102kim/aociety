@echo off
chcp 65001 >nul
title Aociety - 全管线启动
echo =============================================
echo   Aociety - 情感AI世界 (全管线)
echo   摄像头 + 麦克风 + ASR + GLM 5.2
echo =============================================
echo.

cd /d %~dp0

:: 加载 .env
if exist .env (
    for /f "tokens=*" %%a in (.env) do set %%a
)

echo [服务端口]
echo   主后端:      %AOCIETY_PORT% (默认8000)
echo.
echo [模型状态]
if exist models\ferplus\emotion-ferplus-8.onnx (
    echo   FER+ 表情模型: 已就绪
) else ( echo   FER+ 表情模型: 未找到 )

if exist models\mediapipe\face_landmarker.task (
    echo   MediaPipe 人脸: 已就绪
) else ( echo   MediaPipe 人脸: 未找到 )

if exist models\asr\sherpa\sherpa-onnx-paraformer-zh-small-2024-03-09\model.int8.onnx (
    echo   ASR 语音转文字: 已就绪
) else ( echo   ASR 语音转文字: 未找到 )
echo.

echo [1/2] 启动主后端...
start "Aociety-Backend" cmd /c "uvicorn backend.main:app --host 0.0.0.0 --port %AOCIETY_PORT% --reload --log-level info"

echo 等待后端就绪...
:wait_loop
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:%AOCIETY_PORT%/health >nul 2>&1
if errorlevel 1 goto wait_loop

echo 后端已就绪!
echo.

echo [2/2] 启动情感计算管线 (摄像头+麦克风+ASR)...
echo   提示: 如果报错请确保摄像头和麦克风未被其他程序占用
start "Aociety-Pipeline" cmd /c "python -m services.emotion_pipeline --backend http://127.0.0.1:%AOCIETY_PORT%"

timeout /t 3 /nobreak >nul

echo.
echo =============================================
echo  全部启动完成!
echo.
echo  测试接口:
echo    curl http://127.0.0.1:%AOCIETY_PORT%/health
echo    curl -X POST http://127.0.0.1:%AOCIETY_PORT%/emotion/analyze ^
echo      -H "Content-Type: application/json" ^
echo      -d "{\"text_hint\":\"今天好累啊\"}"
echo.
echo  按任意键停止所有服务...
pause >nul

echo 正在停止服务...
taskkill /fi "WINDOWTITLE eq Aociety-Backend" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq Aociety-Pipeline" /f >nul 2>&1
echo 已停止。
