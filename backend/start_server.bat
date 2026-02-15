@echo off
chcp 65001 >nul
echo 启动后端服务器（无自动重载）...
echo 按 Ctrl+C 可正常退出
echo.

call conda activate multimodal-docqa
uvicorn app.main:app --host 0.0.0.0 --port 8000

