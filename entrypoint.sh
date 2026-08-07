#!/bin/sh
# 1. 在背景啟動 MCP Server
python -m src.mcp_server.server &

sleep 2

# 2. 啟動 FastAPI 主服務
exec python3 ./src/api/agent_server.py