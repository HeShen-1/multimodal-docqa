@echo off
chcp 65001 >nul
REM 启动所有必需的后台服务（PostgreSQL, Redis, Celery）

echo ========================================
echo 启动多模态文档问答系统服务
echo ========================================
echo.

REM 检查Docker
echo [1/3] 检查Docker状态...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker未安装或未运行
    echo 请安装Docker Desktop并启动
    pause
    exit /b 1
)
echo ✅ Docker可用

echo.
echo [2/3] 启动Docker服务（PostgreSQL + Redis + Celery）...
docker-compose up -d postgres redis celery-worker

if errorlevel 1 (
    echo ❌ 服务启动失败
    pause
    exit /b 1
)

echo.
echo [3/3] 等待服务就绪...
:wait_loop
timeout /t 2 /nobreak >nul
docker inspect multimodal-docqa-postgres --format "{{.State.Health.Status}}" 2>nul | findstr "healthy" >nul
if errorlevel 1 goto wait_loop
docker inspect multimodal-docqa-redis --format "{{.State.Health.Status}}" 2>nul | findstr "healthy" >nul
if errorlevel 1 goto wait_loop

echo ✅ 所有服务已就绪

echo.
echo ========================================
echo 服务状态
echo ========================================
docker-compose ps

echo.
echo ========================================
echo 服务已启动
echo ========================================
echo.
echo 运行中的服务：
echo   - PostgreSQL: localhost:5432
echo   - Redis: localhost:6379
echo   - Celery Worker: Docker容器
echo.
echo 下一步：
echo   启动API服务器: start_server.bat
echo   或手动启动: python -m uvicorn app.main:app --reload
echo.
echo 查看日志：
echo   docker-compose logs -f
echo   docker-compose logs -f celery-worker
echo.
echo 停止服务：
echo   stop_services.bat
echo.
pause
