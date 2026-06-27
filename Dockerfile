# 使用官方輕量級 Python 3.11 鏡像
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安裝基礎系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴清單並安裝
# 💡 提示：請確保你的 requirements.txt 裡同時包含了：
# 1. 大腦依賴 (fastapi, uvicorn, langgraph)
# 2. MCP 依賴 (mcp, httpx)
# 3. Web 應用依賴 (例如 sqlmodel, pymysql 等業務所需套件)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 複製專案所有原始碼（包含你的 api/, core/, mcp-server/, web_app/ 等）
COPY . .

# 🌟 關鍵：設定 PYTHONPATH，這樣 Docker 內部才能正確找到 src 模組
ENV PYTHONPATH=/app

# 暴露所有可能用到的埠口（8000:Agent, 8001:MCP, 5000:WebApp, 8501:Streamlit預設）
EXPOSE 8000
EXPOSE 8001
EXPOSE 5000
EXPOSE 8501

# 🌟 預設直接啟動這個全功能單體
CMD ["streamlit", "run", "./src/main.py", "--server.address", "0.0.0.0", "--server.port", "8501"]