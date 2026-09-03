#!/bin/sh
# 1. 在背景啟動 MCP Server
python -m src.mcp_server.server &

# 2. 在背景啟動 Celery/Task Worker
python -m src.core.voyager_agent.worker &  # 或 python ./src/worker/worker.py & （依據你的專案目錄結構）

sleep 2

# 3. 啟動 FastAPI 主服務 (使用 exec 讓 FastApi 成為 foreground 主進程)
exec python3 ./src/api/agent_server.py