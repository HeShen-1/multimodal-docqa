@echo off
chcp 65001 >nul
REM ============================================
REM Phase 1 快速配置脚本
REM ============================================
REM 此脚本帮助你快速配置 Phase 1 环境

echo ========================================
echo Phase 1: 用户认证与权限管理 - 快速配置
echo ========================================
echo.

REM 1. 检查 .env 文件
echo [1/5] 检查环境变量配置...
if exist ".env" (
    echo   √ .env 文件已存在
) else (
    echo   ! .env 文件不存在，正在从模板创建...
    copy ".env.example" ".env" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   √ .env 文件已创建，请编辑并配置数据库密码和密钥
        echo   提示：使用以下命令生成安全密钥：
        echo   python -c "import secrets; print(secrets.token_urlsafe(32))"
    ) else (
        echo   × 创建 .env 文件失败
    )
)

REM 2. 检查 PostgreSQL
echo.
echo [2/5] 检查 PostgreSQL 连接...
set PGPASSWORD=123456
psql -h localhost -U postgres -d postgres -c "SELECT 1;" >nul 2>&1
if %errorlevel% equ 0 (
    echo   √ PostgreSQL 连接成功
) else (
    echo   × PostgreSQL 连接失败，请检查配置
    echo   ! 请确保 PostgreSQL 服务已启动
)

REM 3. 检查 Redis
echo.
echo [3/5] 检查 Redis 连接...
python -c "import redis; r = redis.Redis(host='localhost', port=6379, decode_responses=True); r.ping()" >nul 2>&1
if %errorlevel% equ 0 (
    echo   √ Redis 连接成功
) else (
    echo   × Redis 连接失败
    echo   ! 请确保 Redis 服务已启动
)

REM 4. 检查 Python 依赖
echo.
echo [4/5] 检查 Python 依赖...
set missing_packages=
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 set missing_packages=%missing_packages% fastapi
python -c "import sqlalchemy" >nul 2>&1
if %errorlevel% neq 0 set missing_packages=%missing_packages% sqlalchemy
python -c "import redis" >nul 2>&1
if %errorlevel% neq 0 set missing_packages=%missing_packages% redis
python -c "import jose" >nul 2>&1
if %errorlevel% neq 0 set missing_packages=%missing_packages% python-jose
python -c "import passlib" >nul 2>&1
if %errorlevel% neq 0 set missing_packages=%missing_packages% passlib
python -c "import slowapi" >nul 2>&1
if %errorlevel% neq 0 set missing_packages=%missing_packages% slowapi

if "%missing_packages%"=="" (
    echo   √ 所有依赖已安装
) else (
    echo   ! 缺少依赖:%missing_packages%
    echo   运行: pip install -r requirements.txt
)

REM 5. 下一步提示
echo.
echo [5/5] 下一步操作：
echo   1. 编辑 .env 文件，配置数据库密码和密钥
echo   2. 创建数据库：
echo      psql -U postgres -c "CREATE DATABASE multimodal_docqa;"
echo   3. 初始化数据库表：
echo      python scripts\init_auth_db.py
echo   4. 启动服务：
echo      python -m app.main
echo   5. 访问 API 文档：
echo      http://localhost:8000/docs

echo.
echo ========================================
echo 配置检查完成！
echo ========================================
echo.
pause

