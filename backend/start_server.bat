@echo off
chcp 65001 >nul
REM 启动FastAPI开发服务器

echo ========================================
echo 启动FastAPI开发服务器
echo ========================================
echo.

REM 激活conda环境
call conda activate multimodal-docqa
if errorlevel 1 (
    echo ❌ 无法激活conda环境
    pause
    exit /b 1
)

echo 启动服务器（支持热重载）...
echo 访问地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务器
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
