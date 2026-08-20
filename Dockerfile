# 使用官方輕量級 Python 3.11 鏡像
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV TZ=UTC

# 安裝基礎系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 從官方 uv 鏡像直接複製 uv 執行檔（比 pip install uv 更快更穩定）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 複製依賴描述文件
COPY pyproject.toml uv.lock ./

# 🌟 匯出 uv.lock 內容並安裝至系統全域
RUN uv export --frozen --no-dev -o requirements.txt && \
    uv pip install --system -r requirements.txt

# 複製專案所有原始碼
COPY . .

# 設定 PYTHONPATH
ENV PYTHONPATH=/app

# EXPOSE 主要提供給本地測試參考，Render 會自動分配 PORT
EXPOSE 8000
EXPOSE 8001
EXPOSE 5000
EXPOSE 8501

# 確保 entrypoint.sh 有執行權限
RUN chmod +x ./entrypoint.sh

# 將 CMD 改為執行 entrypoint.sh
CMD ["./entrypoint.sh"]