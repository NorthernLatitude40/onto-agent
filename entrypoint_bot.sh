#!/bin/sh
set -e

# 1. 打印启动日志（可选）
echo "Starting Discord Bot Service on Hugging Face..."

# 2. 启动主程序 (Discord Bot + 7860端口健康检查)
# 使用 exec 让 Python 进程成为 PID 1 主进程，正确接收容器退出信号 (SIGTERM)
exec python -m src.bot.main