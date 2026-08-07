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

# 從官方 uv 鏡像直接複製 uv 執行檔（比 pip install uv 更快更穩定）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 複製依賴描述文件
COPY pyproject.toml uv.lock ./

# 使用 uv 將套件安裝至全域 Python 環境 (system)
RUN uv sync --frozen --system

# 複製專案所有原始碼
COPY . .

# 設定 PYTHONPATH
ENV PYTHONPATH=/app

# EXPOSE 主要提供給本地測試參考，Render 會自動分配 PORT
EXPOSE 8000
EXPOSE 8001
EXPOSE 5000
EXPOSE 8501

CMD ["python3", "./src/api/agent_server.py"]