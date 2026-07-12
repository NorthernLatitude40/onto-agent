#!/bin/sh

# 1. 啟動 FastAPI，讓它在背景執行 (&)
# 並且將輸出導向到日誌檔案或是繼續保留在終端機中
echo "🚀 Starting Backend API..."
python3 ./src/api/agent_server.py > ./backend.log 2>&1 &

# 2. 為了確保 FastAPI 有時間啟動，可以加一個短暫等待
sleep 3

# 3. 執行原本 Dockerfile 中定義的 CMD 指令
# 使用 exec 可以確保 Streamlit 接收到 Docker 的停止信號 (SIGTERM)
echo "🎨 Starting Streamlit UI..."
exec streamlit run ./src/main.py --server.address 0.0.0.0 --server.port 8501