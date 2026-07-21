import os
import sys
import logging
import time
import traceback  # 新增：用於記錄詳細錯誤堆疊
from typing import List, Union

import pymysql
from neo4j import GraphDatabase
import requests
from fastmcp import FastMCP

# 假設這些模組在你的專案路徑中
from src.ontology.interface.graph_ingestion_tools import GraphIngestionTools
from src.ontology.interface.ontology.output_contract import MappingRule

# ==========================================
# 1. 日誌配置
# ==========================================
log_file = os.path.join(os.path.dirname(__file__), "mcp_server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),  # 同時印到終端機方便觀察
    ],
)

# ==========================================
# 2. 實例化 FastMCP 與連線設定
# ==========================================
mcp = FastMCP("Ontology MCP")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "172.17.0.1"),
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "my_agent_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
ingestion_toolbox = GraphIngestionTools(neo4j_driver=driver)


# ==========================================
# 3. MySQL 輔助函數 (統一錯誤處理)
# ==========================================
def get_db_connection():
    """統一獲取資料庫連接的輔助方法，包含連線日誌"""
    try:
        logging.info(
            f"正在嘗試連接 MySQL -> host: {DB_CONFIG['host']}, db: {DB_CONFIG['database']}"
        )
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logging.error("!!! MySQL 連線失敗 !!!")
        logging.error(f"錯誤訊息: {str(e)}")
        logging.error(traceback.format_exc())
        raise e

# ==========================================
# 3. 核心功能：大數據圖譜構建雙工具
# ==========================================


@mcp.tool()
def inspect_excel_schema(file_path: str) -> str:
    """
    當使用者提供一個 Excel 檔案路徑時，優先使用此工具。
    它會掃描 Excel 並回傳所有工作表(Sheets)的名稱、欄位名稱與系統標準型態。
    """
    return ingestion_toolbox.inspect_dataset_schema(file_path)


@mcp.tool()
def execute_excel_to_graph(file_path: str, mapping_rules: List[MappingRule]) -> str:
    """
    在分析完 Schema 並決定好圖對應規則(Mapping Rules)後，使用此工具將 rows 全量寫入 Neo4j。

    Args:
        file_path: Excel 檔案路徑。
        mapping_rules: 格式必須嚴格遵守以下範例：
        [
            {
                "source_sheet": "Orders",
                "map_to_node": [{"concept_id": "ns0__VIPCustomer", "primary_key": "customer_id"}],
                "map_to_edge": [{"source_key": "customer_id", "target_key": "product_id", "relationship_id": "ns0__bought"}]
            }
        ]
    """
    return ingestion_toolbox.execute_graph_ingestion(file_path, mapping_rules)

# ==========================================
# 4. MySQL 工具功能
# ==========================================


@mcp.tool()
def query_mysql(sql_query: str) -> str:
    """僅供系統管理員查詢統計/後台資料。"""
    if not sql_query.strip().lower().startswith(("select", "show")):
        return "錯誤：僅允許執行 SELECT 或 SHOW 查詢。"

    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(sql_query)
            return str(cursor.fetchall())
    except Exception as e:
        return f"資料庫查詢錯誤: {str(e)}"
    finally:
        if connection and connection.open:
            connection.close()


@mcp.tool()
def find_user_by_username(username: str) -> str:
    """根據使用者名稱查詢會員資訊。"""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            return str(cursor.fetchall())
    except Exception as e:
        return f"查詢會員失敗: {str(e)}"
    finally:
        if connection and connection.open:
            connection.close()

@mcp.tool()
def find_product_by_name(product_name: str) -> str:
    """
    根據商品名稱模糊查詢商品資訊。
    例如：The Jandal, The Jandal (Winter Edition)
    回傳：product_id, price, stock
    """
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            # 修正原本殘缺的 SQL，改用安全的參數化查詢
            sql = "SELECT product_id, price, stock FROM products WHERE product_name LIKE %s"
            cursor.execute(sql, (f"%{product_name}%",))
            result = cursor.fetchall()
            return str(result)
    except Exception as e:
        return f"錯誤: {e}"
    finally:
        if "connection" in locals() and connection.open:
            connection.close()

@mcp.tool()
def create_agent_order(user_id: int, product_id: int, quantity: int) -> str:
    """建立訂單並返回付款連結。"""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 獲取價格
            cursor.execute(
                "SELECT price FROM products WHERE product_id = %s", (product_id,)
            )
            product = cursor.fetchone()
            if not product:
                return f"錯誤：找不到商品 ID {product_id}。"

            price = float(product["price"])
            total = round(quantity * price, 2)

            # 寫入主表
            cursor.execute(
                "INSERT INTO `orders` (`user_id`, `order_date`, `total_amount`, `status`) VALUES (%s, %s, %s, 'PENDING')",
                (user_id, time.strftime("%Y-%m-%d"), total),
            )
            new_id = cursor.lastrowid

            # 寫入明細
            cursor.execute(
                "INSERT INTO `order_items` (`order_id`, `product_id`, `quantity`, `price_per_unit`) VALUES (%s, %s, %s, %s)",
                (new_id, product_id, quantity, price),
            )
            connection.commit()
            return f"訂單 {new_id} 建立成功。付款連結: http://localhost:5000/mock-pay-page?order_id={new_id}"
    except Exception as e:
        if connection:
            connection.rollback()
        logging.error(f"訂單創建失敗: {traceback.format_exc()}")
        return f"建立訂單失敗: {str(e)}"
    finally:
        if connection and connection.open:
            connection.close()


@mcp.tool()
def get_order_by_id(order_id: int) -> str:
    """
    根據訂單 ID 查詢訂單詳情與明細（包含主表與明細表聯查）。
    """
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            sql = """
            SELECT o.order_id, o.user_id, o.order_date, o.total_amount, o.status,
                   oi.product_id, oi.quantity, oi.price_per_unit
            FROM orders o
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_id = %s
            """
            cursor.execute(sql, (order_id,))
            result = cursor.fetchall()
            if not result:
                return f"找不到訂單 ID: {order_id} 的資料。"
            return str(result)
    except Exception as e:
        return f"錯誤: {e}"
    finally:
        if "connection" in locals() and connection.open:
            connection.close()


# ==========================================
# 5. 核心功能：紐西蘭旅遊特惠本體推理工具
# ==========================================


@mcp.tool()
def get_tour_deals_by_city(city_name: str) -> List[str]:
    """
    利用 n10s 本體推理，查詢指定城市出發或全局的紐西蘭旅遊特惠行程（Deals）。
    """
    logging.info(f"[Graph Query] 進入優化推理 - 目標城市/概念: '{city_name}'")
    search_name = city_name.strip()

    is_global_query = search_name.lower() in ["city", "tourdeal", "hoponhopoffdeal"]

    cypher_base = """
    MATCH (dealClass:owl__Class) WHERE dealClass.uri ENDS WITH "TourDeal"
    MATCH (cityClass:owl__Class) WHERE cityClass.uri ENDS WITH "City"
    
    MATCH (subDealClass:owl__Class)-[:rdfs__subClassOf*0..]->(dealClass)
    MATCH (subCityClass:owl__Class)-[:rdfs__subClassOf*0..]->(cityClass)
    
    WITH split(subDealClass.uri, "/")[-1] AS subDealLabel, 
         split(subCityClass.uri, "/")[-1] AS subCityLabel
    
    MATCH (d:Resource)-[r]->(c:Resource)
    WHERE type(r) ENDS WITH "startsFrom"
      {filter_clause}
      AND any(lbl IN labels(d) WHERE lbl ENDS WITH subDealLabel)
      AND any(lbl IN labels(c) WHERE lbl ENDS WITH subCityLabel)
      
    RETURN DISTINCT d.rdfs__label AS deal_name, 
                    c.rdfs__label AS city_name, 
                    d.ns0__priceNZD AS price, 
                    d.ns0__durationDays AS days,
                    d.ns0__discountPercent AS discount
    """

    if is_global_query:
        query = cypher_base.format(filter_clause="")
        params = {}
    else:
        filter_clause = "AND (c.uri ENDS WITH $city_name OR c.rdfs__label = $city_name)"
        query = cypher_base.format(filter_clause=filter_clause)
        params = {"city_name": search_name}

    try:
        with driver.session() as session:
            result = session.run(query, **params)
            records_list = []

            for record in result:
                d_name = record["deal_name"]
                c_name = record["city_name"]
                price = record["price"]
                days = record["days"]
                discount = record["discount"]

                if is_global_query:
                    records_list.append(
                        f"行程:{d_name}(出發自:{c_name}) | 天數:{days}天 | 價格:{price}NZD | 折扣:{discount}%"
                    )
                else:
                    records_list.append(
                        f"行程:{d_name} | 天數:{days}天 | 價格:{price}NZD | 折扣:{discount}%"
                    )

            return records_list

    except Exception as e:
        logging.error(f"Neo4j 執行推理失敗: {e}", exc_info=True)
        return [f"ERROR: {str(e)}"]


# ==========================================
# 6. 擴展的瀏覽器搜尋工具
# ==========================================
@mcp.tool()
def web_search(query: str, max_results: int = 3) -> str:
    """
    當使用者詢問最新消息、即時資訊、時事，或是需要從網路上搜尋、查證資料時，使用此工具。
    請一律使用條列式（Bullet points）或普通字體呈現。嚴禁使用 #, ##, ### 等標題語法。
    """
    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        return "錯誤：找不到 TAVILY_API_KEY 環境變數。請先設定 API 金鑰。"

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            return f"針對 '{query}' 沒有找到相關的搜尋結果。"

        formatted_outputs = []
        for i, res in enumerate(results, 1):
            formatted_outputs.append(
                f"[{i}] 標題: {res.get('title')}\n"
                f"    網址: {res.get('url')}\n"
                f"    摘要: {res.get('content')}\n"
                f"---"
            )

        return "\n".join(formatted_outputs)

    except Exception as e:
        return f"搜尋過程中發生錯誤: {str(e)}"

# ==========================================
# 7. 啟動
# ==========================================
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001)
