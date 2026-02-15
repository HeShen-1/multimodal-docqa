@echo off
chcp 65001 >nul
echo ========================================
echo Phase 2 快速部署脚本 - 对话管理功能
echo ========================================
echo.

echo [1/3] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python，请先安装Python 3.11+
    pause
    exit /b 1
)
echo ✅ Python环境正常

echo.
echo [2/3] 初始化数据库表...
echo 正在创建conversations和messages表...
python scripts\init_conversation_db.py
if errorlevel 1 (
    echo ❌ 数据库初始化失败
    pause
    exit /b 1
)

echo.
echo [3/3] 启动服务...
echo.
echo ========================================
echo Phase 2 部署完成！
echo ========================================
echo.
echo 接下来请手动启动服务：
echo   python -m app.main
echo.
echo 或使用uvicorn：
echo   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo API文档地址：
echo   http://localhost:8000/docs
echo.
echo 快速启动指南：
echo   Phase\QUICKSTART_PHASE2.md
echo.
pause

