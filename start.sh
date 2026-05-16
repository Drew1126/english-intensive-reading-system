#!/bin/bash

echo "正在启动 Linux 版服务..."
echo "请确保已安装 Python3 和依赖: pip3 install -r requirements.txt"

cd "$(dirname "$0")/backend" || exit

if [ ! -f ".env" ]; then
    echo "未找到 .env 文件，请复制 .env.example 为 .env 并填入 API Key！"
    exit 1
fi

echo "服务启动成功！访问: http://localhost:8000"
echo "按 Ctrl+C 停止服务"

# 生产模式：去掉 --reload，保证长期运行稳定
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log
