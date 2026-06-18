import os
import sys
import logging
import time
import pymysql
from fastapi import FastAPI
import uvicorn
from mcp.server.fastmcp import FastMCP

# 日誌配置
log_file = os.path.join(os.path.dirname(__file__), "mcp_server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8")],
)

mcp = FastMCP("Agent-Core-Server")

app = FastAPI()

# 把 MCP 挂到 FastAPI
app.mount("/", mcp.sse_app())  # 如果你的版本支持

# 資料庫連線設定
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "my_agent_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


@app.get("/health")
def health():
    return {"status": "ok"}


# ==========================================
# 核心功能一：原有的 MySQL 創建與寫入工具
# ==========================================


@mcp.tool()
def query_mysql(sql_query: str) -> str:
    """執行 MySQL 唯讀查詢語法（例如 SELECT）。"""
    clean_query = sql_query.strip().lower()
    if not clean_query.startswith("select") and not clean_query.startswith("show"):
        return "錯誤：僅允許執行 SELECT 或 SHOW 查詢。"
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute(sql_query)
            return str(cursor.fetchall())
    except Exception as e:
        return f"錯誤: {str(e)}"
    finally:
        if "connection" in locals() and connection.open:
            connection.close()


@mcp.tool()
def create_agent_order(
    user_id: int, product_id: int, quantity: int, price_per_unit: float
) -> str:
    """
    當使用者想要購買某個商品時呼叫。
    此工具會自動計算總價，並同時寫入 MySQL 的 orders 主表與 order_items 明細表（主從表聯動），並返回付款連結。
    """
    logging.info(f"======== 收到 Agent 聯動創建訂單請求 ========")
    total_amount = round(quantity * price_per_unit, 2)
    current_date = time.strftime("%Y-%m-%d")

    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            # 1. 寫入 orders 主表
            sql_order = "INSERT INTO `orders` (`user_id`, `order_date`, `total_amount`, `status`) VALUES (%s, %s, %s, 'PENDING')"
            cursor.execute(sql_order, (user_id, current_date, total_amount))

            # 2. 獲取自增產生的 order_id
            new_order_id = cursor.lastrowid

            # 3. 寫入 order_items 明細表
            sql_item = "INSERT INTO `order_items` (`order_id`, `product_id`, `quantity`, `price_per_unit`) VALUES (%s, %s, %s, %s)"
            cursor.execute(
                sql_item, (new_order_id, product_id, quantity, price_per_unit)
            )

            connection.commit()

        logging.info(f"成功聯動寫入 MySQL！主表訂單 ID: {new_order_id}。")

        # 指向獨立出來的 Flask 5000 埠口網址
        base_url = "http://localhost:5000"
        mock_pay_url = f"{base_url}/mock-pay-page?order_id={new_order_id}"

        return (
            f"【系統通知】訂單已成功同步寫入 MySQL 資料庫！\n"
            f"✨ 生成系統訂單 ID: {new_order_id}\n"
            f"👤 用戶 ID: {user_id}\n"
            f"💰 訂單總金額: {total_amount} 元\n\n"
            f"請引導使用者點擊以下連結進行模擬支付：\n{mock_pay_url}"
        )

    except Exception as e:
        logging.error(f"寫入資料庫失敗: {e}", exc_info=True)
        return f"建立訂單失敗，資料庫寫入異常: {str(e)}"
    finally:
        if "connection" in locals() and connection.open:
            connection.close()


# ================= 3. 啟動內建網路伺服器 =================
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
