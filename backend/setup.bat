@echo off
chcp 65001 >nul
REM 统一环境配置脚本 - 支持所有Phase

if "%1"=="" (
    echo 用法: setup.bat [phase_number]
    echo 示例: setup.bat 1  - 配置Phase 1（用户认证）
    echo       setup.bat 2  - 配置Phase 2（对话管理）
    echo       setup.bat 3  - 配置Phase 3（缓存优化）
    echo       setup.bat 4  - 配置Phase 4（文档管理增强）
    echo.
    echo 或完整配置: setup.bat full
    pause
    exit /b 1
)

echo ========================================
echo 多模态文档问答系统 - 环境配置
echo ========================================
echo.

REM 激活conda环境
echo [1/5] 激活conda环境...
call conda activate multimodal-docqa
if errorlevel 1 (
    echo ❌ 错误: 无法激活conda环境
    echo 请先创建环境: conda create -n multimodal-docqa python=3.11
    pause
    exit /b 1
)
echo ✅ 环境激活成功

REM 检查.env文件
echo.
echo [2/5] 检查配置文件...
if not exist ".env" (
    echo 创建.env文件...
    copy ".env.example" ".env" >nul 2>&1
    if errorlevel 1 (
        echo ❌ 创建.env文件失败
        pause
        exit /b 1
    )
    echo ✅ .env文件已创建，请编辑配置
) else (
    echo ✅ .env文件已存在
)

REM 安装依赖
echo.
echo [3/5] 安装Python依赖...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✅ 依赖安装完成

REM 检查服务
echo.
echo [4/5] 检查必需服务...

REM 检查PostgreSQL
python -c "import psycopg2; conn = psycopg2.connect('host=localhost port=5432 user=postgres password=123456'); conn.close()" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  PostgreSQL未连接，请确保服务已启动
) else (
    echo ✅ PostgreSQL连接正常
)

REM 检查Redis
python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping()" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Redis未连接，请确保服务已启动
) else (
    echo ✅ Redis连接正常
)

REM 初始化数据库
echo.
echo [5/5] 初始化数据库...

if "%1"=="full" (
    echo 初始化所有Phase数据库表...
    python scripts/init_auth_db.py
    python scripts/init_conversation_db.py
    python scripts/init_phase4_db.py
) else if "%1"=="1" (
    echo 初始化Phase 1数据库表（用户认证）...
    python scripts/init_auth_db.py
) else if "%1"=="2" (
    echo 初始化Phase 2数据库表（对话管理）...
    python scripts/init_conversation_db.py
) else if "%1"=="3" (
    echo Phase 3无需额外数据库初始化
) else if "%1"=="4" (
    echo 初始化Phase 4数据库表（标签、分享）...
    python scripts/init_phase4_db.py
) else (
    echo ❌ 无效的Phase编号: %1
    pause
    exit /b 1
)

if errorlevel 1 (
    echo ❌ 数据库初始化失败
    pause
    exit /b 1
)
echo ✅ 数据库初始化完成

echo.
echo ========================================
echo 配置完成！
echo ========================================
echo.
echo 下一步操作：
echo   1. 启动服务: start_services.bat
echo   2. 启动API服务器: start_server.bat
echo   3. 访问API文档: http://localhost:8000/docs
echo   4. 运行测试: run_tests.bat %1
echo.
echo 详细文档: Phase\QUICKSTART_PHASE%1.md
echo.
pause
