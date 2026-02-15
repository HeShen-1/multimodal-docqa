@echo off
chcp 65001 >nul
REM Phase 3 Test Runner Script

echo ========================================
echo Phase 3 Tests - Cache Optimization System
echo ========================================
echo.

REM Activate environment
call conda activate multimodal-docqa
if errorlevel 1 (
    echo Error: Cannot activate environment
    pause
    exit /b 1
)

echo Running Phase 3 test suite...
echo.

REM Run tests
pytest tests/test_phase3.py -v -s --tb=short --color=yes

echo.
echo ========================================
echo Test Complete
echo ========================================
echo.
pause
