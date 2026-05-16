@echo off
echo 启动中...
echo 访问 http://localhost:8000
cd /d "%~dp0backend"
start http://localhost:8000
py -m uvicorn main:app --reload --port 8000
pause
