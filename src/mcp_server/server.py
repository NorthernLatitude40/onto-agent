import os
import sys
import logging
import time
import pymysql
from fastapi import FastAPI
import uvicorn
from mcp.server.fastmcp import FastMCP
from src.mcp_server.graph_data import graph
from neo4j import GraphDatabase

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

# 1. 在模块全局加载时，初始化 Driver
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# 全局唯一的 driver 实例
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


@app.get("/health")
def health():
    return {"status": "ok"}


# ==========================================
# 核心功能一：原有的 MySQL 創建與寫入工具
# ==========================================


@mcp.tool()
def query_mysql(sql_query: str) -> str:
    """
    僅用於常規快捷工具無法覆蓋的、極度複雜的後台數據庫管理、財務報表統計或系統維護。
    絕對不能用於查詢客戶與商品的購買歷史或名下資產。
    """
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


@mcp.tool()
def get_customer_products(name: str) -> list:
    """
    利用 n10s 本体推理，查询指定客户或全局概念的购买记录。
    核心业务工具：查询客户（Customer/VIPCustomer等）与商品（Product/ElectronicProduct等）之间的购买记录。
    支持传入具体人名（如 ZhangSan1），也支持传入全局概念名称（如 Customer 或 VIPCustomer）。
    只要用户提问涉及“谁买了什么”、“哪些人买了什么商品”、“语义推理查询”，必须且只能调用此工具。
    """
    print("\n" + "="*50)
    print(f"[LOG] 工具进入 - 目标名称: '{name}'")
    
    search_name = name.strip()
    
    # 转换为小写判断是否为全局本体概念
    is_global_query = search_name.lower() in ["customer", "vipcustomer", "product", "electronicproduct"]
    
    if is_global_query:
        print("[LOG] 判定结果: 全局本体概念推理")
        query = """
        // 1. 锁成本体中的基类 Customer 和 Product
        MATCH (customerClass:owl__Class) WHERE customerClass.uri ENDS WITH "Customer"
        MATCH (productClass:owl__Class) WHERE productClass.uri ENDS WITH "Product"
        
        // 2. 找到它们所有的特化子类（*0.. 表示包含自身）
        MATCH (subCustomerClass:owl__Class)-[:rdfs__subClassOf*0..]->(customerClass)
        MATCH (subProductClass:owl__Class)-[:rdfs__subClassOf*0..]->(productClass)
        
        // 3. 修正 Cypher 语法：使用 split(str, delimiter)[-1] 提取末尾标签名
        WITH split(subCustomerClass.uri, "/")[-1] AS subCustomerLabel, 
             split(subProductClass.uri, "/")[-1] AS subProductLabel
        
        // 4. 从子类名称反推具有该标签的实例节点并匹配购买关系
        MATCH (c:Resource)-[r]->(p:Resource)
        WHERE type(r) ENDS WITH "bought"
          AND any(lbl IN labels(c) WHERE lbl ENDS WITH subCustomerLabel)
          AND any(lbl IN labels(p) WHERE lbl ENDS WITH subProductLabel)
          
        RETURN c.uri AS customer_uri, p.uri AS product_uri
        """
        params = {}
    else:
        print(f"[LOG] 判定结果: 具体实例精准查询 -> {search_name}")
        query = """
        MATCH (customerClass:owl__Class) WHERE customerClass.uri ENDS WITH "Customer"
        MATCH (productClass:owl__Class) WHERE productClass.uri ENDS WITH "Product"
        
        MATCH (subCustomerClass:owl__Class)-[:rdfs__subClassOf*0..]->(customerClass)
        MATCH (subProductClass:owl__Class)-[:rdfs__subClassOf*0..]->(productClass)
        
        // 修正 Cypher 语法：使用 split(str, delimiter)[-1]
        WITH split(subCustomerClass.uri, "/")[-1] AS subCustomerLabel, 
             split(subProductClass.uri, "/")[-1] AS subProductLabel
        
        MATCH (c:Resource)-[r]->(p:Resource)
        WHERE type(r) ENDS WITH "bought"
          AND (c.uri ENDS WITH $customer_name OR c.rdfs__label = $customer_name)
          AND any(lbl IN labels(c) WHERE lbl ENDS WITH subCustomerLabel)
          AND any(lbl IN labels(p) WHERE lbl ENDS WITH subProductLabel)
          
        RETURN c.uri AS customer_uri, p.uri AS product_uri
        """
        params = {"customer_name": search_name}

    try:
        with driver.session() as session:
            result = session.run(query, **params)
            records_list = []
            
            for record in result:
                c_uri = record["customer_uri"]
                p_uri = record["product_uri"]
                print(f"[LOG] 成功推理召回数据 -> 客户: {c_uri}, 商品: {p_uri}")
                
                # Python 层的 URI 清洗
                c_name = c_uri.split("/")[-1] if "/" in c_uri else c_uri
                p_name = p_uri.split("/")[-1] if "/" in p_uri else p_uri
                
                if is_global_query:
                    records_list.append(f"{c_name}(购买了){p_name}")
                else:
                    records_list.append(p_name)
                    
            print(f"[LOG] 最终返回给 Agent 的数据: {records_list}")
            print("="*50 + "\n")
            return records_list
            
    except Exception as e:
        print(f"[ERROR] 执行失败: {str(e)}")
        print("="*50 + "\n")
        return [f"ERROR: {str(e)}"]


# ================= 3. 啟動內建網路伺服器 =================
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
