import os
import sys
import logging
import time
from typing import List, Union

import pymysql
from neo4j import GraphDatabase

# FastMCP 統一導入
from fastmcp import FastMCP

# 引入抽離出來的獨立工具類別與參數契約
from src.mcp_server.tools.graph_ingestion_tools import GraphIngestionTools
from src.ingestion.interface.ontology.output_contract import MappingRule
import requests

# ==========================================
# 1. 日誌配置
# ==========================================
log_file = os.path.join(os.path.dirname(__file__), "mcp_server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8")],
)

# ==========================================
# 2. 實例化 FastMCP 伺服器
# ==========================================
# FastMCP 3.4.2+ 自帶整合，不需手動寫額外的 FastAPI app
mcp = FastMCP("Ontology MCP")

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

# Neo4j 連線設定
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# 全局唯一的 driver 實例
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# 實例化圖匯入工具箱，共享全局唯一的 driver
ingestion_toolbox = GraphIngestionTools(neo4j_driver=driver)


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
    # FastMCP 會依據 Pydantic / Type Hints 自動將傳入的 JSON 轉為對應的 MappingRule 結構
    return ingestion_toolbox.execute_graph_ingestion(file_path, mapping_rules)


# ==========================================
# 4. 核心功能：MySQL 創建與寫入工具
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
    logging.info("======== 收到 Agent 聯動創建訂單請求 ========")
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


# ==========================================
# 5. 核心功能：紐西蘭旅遊特惠本體推理工具
# ==========================================


@mcp.tool()
def get_tour_deals_by_city(city_name: str) -> List[str]:
    """
    利用 n10s 本體推理，查詢指定城市出發或全局的紐西蘭旅遊特惠行程（Deals）。
    只要用戶提問涉及“從哪裡出發有什麼行程”、“某城市的旅遊套裝”、“特惠行程查詢”，必須且只能調用此工具。
    """
    logging.info(f"[Graph Query] 進入優化推理 - 目標城市/概念: '{city_name}'")
    search_name = city_name.strip()

    # 轉換為小寫判斷是否為全局本體概念查詢
    is_global_query = search_name.lower() in ["city", "tourdeal", "hoponhopoffdeal"]

    # 抽取核心的 Cypher 模板以提高可讀性
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
def web_search(query: str, max_results: int = 5) -> str:
    """
    當使用者詢問最新消息、即時資訊、時事，或是需要從網路上搜尋、查證資料時，使用此工具。
    
    Args:
        query: 要搜尋的關鍵字或句子。
        max_results: 回傳的結果數量，預設為 5 筆。
    """
    # 這裡以 Tavily API 為例（專為 LLM 設計的搜尋引擎）
    # 你需要去 https://tavily.com/ 註冊一個免費的 API Key
    api_key = os.environ.get("TAVILY_API_KEY")
    
    if not api_key:
        return "錯誤：找不到 TAVILY_API_KEY 環境變數。請先設定 API 金鑰。"
        
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 解析並格式化搜尋結果
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
# 6. 啟動 FastMCP 伺服器
# ==========================================
if __name__ == "__main__":
    try:
        # FastMCP 內建完美的標準 HTTP/SSE 與 Stdio 傳輸切換機制
        # 移除了原先會報錯的 @app.get 偽代碼，完全託管給 FastMCP
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=8001,
        )
    finally:
        # 確保進程關閉時 Driver 資源能優雅釋放
        driver.close()
