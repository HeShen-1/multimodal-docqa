@echo off
REM Phase 2 API 测试运行脚本
REM 使用 -W ignore 参数抑制测试清理时的无害警告

echo ========================================
echo Phase 2 API test
echo ========================================
echo.

REM 激活 conda 环境
call conda activate multimodal-docqa

REM 运行测试，抑制警告
python -W ignore::Warning -m pytest tests/test_phase2.py -v

echo.
echo ========================================
echo test is finished
echo ========================================

