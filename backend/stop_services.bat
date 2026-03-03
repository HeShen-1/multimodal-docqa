@echo off
chcp 65001 >nul
REM 停止所有服务

echo ========================================
echo 停止多模态文档问答系统服务
echo ========================================
echo.

docker-compose down

if errorlevel 1 (
    echo ❌ 停止服务失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo 所有服务已停止
echo ========================================
echo.
echo 如需删除数据卷（谨慎操作！）：
echo   docker-compose down -v
echo.
pause
