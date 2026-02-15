@echo off
chcp 65001 >nul
REM Phase 3 Setup Script - Cache Optimization System
REM Quick setup and validation for Phase 3

echo ========================================
echo Phase 3 Setup - Cache Optimization System
echo ========================================
echo.

REM Check conda environment
echo [1/5] Checking conda environment...
call conda activate multimodal-docqa
if errorlevel 1 (
    echo Error: Cannot activate multimodal-docqa environment
    echo Please run setup_phase1.bat or setup_phase2.bat first
    pause
    exit /b 1
)
echo OK: conda environment activated
echo.

REM Check Redis
echo [2/5] Checking Redis service...
docker ps | findstr redis-cache >nul 2>&1
if errorlevel 1 (
    echo Redis container not running, starting...
    docker run -d --name redis-cache -p 6379:6379 redis:7-alpine
    if errorlevel 1 (
        echo Warning: Cannot start Redis container
        echo Please start Redis manually or check if Docker is running
        echo Application will run without Redis (local cache only)
    ) else (
        echo OK: Redis container started
        timeout /t 3 >nul
    )
) else (
    echo OK: Redis container is running
)
echo.

REM Check dependencies
echo [3/5] Checking Python dependencies...
python -c "import redis" >nul 2>&1
if errorlevel 1 (
    echo Installing redis dependency...
    pip install redis==5.0.7
)
echo OK: Dependencies check complete
echo.

REM Verify configuration
echo [4/5] Verifying configuration file...
if not exist .env (
    echo Creating .env file...
    (
        echo # Redis Configuration
        echo REDIS_HOST=localhost
        echo REDIS_PORT=6379
        echo REDIS_PASSWORD=
        echo REDIS_DB=0
        echo.
        echo # Cache Configuration
        echo CACHE_ENABLED=true
        echo CACHE_DEFAULT_EXPIRE=1800
        echo CACHE_QUERY_EXPIRE=1800
        echo CACHE_DOCUMENT_EXPIRE=3600
        echo CACHE_USER_EXPIRE=7200
        echo CACHE_MAX_KEYS=10000
    ) > .env
    echo OK: .env file created
) else (
    echo OK: .env file exists
)
echo.

REM Run tests
echo [5/5] Running Phase 3 tests...
echo.
pytest tests/test_phase3.py -v --tb=short
if errorlevel 1 (
    echo.
    echo Warning: Some tests failed
    echo This may be because Redis is not connected, application can still run
) else (
    echo.
    echo OK: All tests passed
)
echo.

echo ========================================
echo Phase 3 Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Start application: python -m uvicorn app.main:app --reload
echo 2. Visit documentation: http://localhost:8000/docs
echo 3. Check cache stats: GET /api/v1/cache/stats
echo.
echo Detailed documentation: Phase/QUICKSTART_PHASE3.md
echo.
pause
