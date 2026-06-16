import logging
import os

# db_mcp_server.py
from mcp.server.fastmcp import FastMCP
import pymysql

# 1. 設定日誌配置：將日誌寫入到當前目錄下的 mcp_server.log 檔案中
# 💡 注意：絕不能輸出到控制台 (StreamHandler)，否則會破壞 MCP 的 stdio 通訊
log_file = os.path.join(os.path.dirname(__file__), "mcp_server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)

# 初始化 MCP Server
mcp = FastMCP("MySQL-Query-Server")

# 資料庫連線設定
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "my_agent_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

@mcp.tool()
def query_mysql(sql_query: str) -> str:
    """
    執行 MySQL 唯讀查詢語法（例如 SELECT）。
    
    Args:
        sql_query (str): 要執行的標準 SQL 查詢語句。
    """
    # 2. 記錄 Agent 傳進來的原始 SQL 到底長怎樣
    logging.info(f"======== 收到 Agent 查詢請求 ========")
    logging.info(f"原始 SQL: {repr(sql_query)}")  # repr 可以把隱藏的換行或特殊字元印出來

    # 安全檢查：限制只能執行唯讀查詢
    clean_query = sql_query.strip().lower()
    if not clean_query.startswith("select") and not clean_query.startswith("show"):
        err_msg = "錯誤：基於安全理由，此工具僅允許執行 SELECT 或 SHOW 查詢。"
        logging.warning(f"安全檢查未通過: {err_msg}")
        return err_msg

    try:
        # 真正開始連線資料庫
        logging.info("正在連線到 MySQL 資料庫...")
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            logging.info(f"正在執行 SQL... ")
            cursor.execute(sql_query)
            result = cursor.fetchall()
            
            # 3. 記錄資料庫返回的原生結果
            logging.info(f"資料庫執行成功！回傳筆數: {len(result)} 筆")
            logging.debug(f"原生結果內容: {result}")
            
            # 如果查出來沒資料，回傳明確的通知
            if not result:
                logging.info("結果為空 (Empty set)")
                return "查詢成功，但資料庫中無對應資料 (Empty set)。"
                
            return str(result)
            
    except Exception as e:
        # 4. 如果報錯，把錯誤訊息完整記下來
        error_msg = f"資料庫執行錯誤: {str(e)}"
        logging.error(error_msg, exc_info=True)  # exc_info 會把詳細的錯誤行數堆疊印出來
        return error_msg
        
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()
            logging.info("資料庫連線已安全關閉。")

if __name__ == "__main__":
    logging.info("MySQL MCP Server 正在啟動...")
    mcp.run()