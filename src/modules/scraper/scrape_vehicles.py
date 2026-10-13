import os
import requests
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def scrape_and_store_vehicles():
    target_url = "https://getlostinnz.co.nz/"  # 或者替换为具体的车型列表页 URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"正在访问目标网站抓取车型数据: {target_url} ...")
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"网络请求失败: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # ---------------------------------------------------------
    # 示例解析逻辑：
    # 实际开发中，你需要根据 getlostinnz.co.nz 页面的实际 HTML 结构
    # 调整 CSS 选择器（例如 soup.select('.vehicle-card') 等）
    # ---------------------------------------------------------
    
    # 这里我们模拟解析出结构化车辆列表（若网站有特定结构，可在此处精准提取）
    # 假设页面上每个车型块都有对应的标题、规格和价格
    scraped_vehicles = [
        {
            "model_name": "Toyota Hiace 2-Berth Campervan",
            "berths": 2,
            "transmission": "Automatic",
            "specs": {"solar": True, "battery": "100Ah", "heater": "Diesel", "bed": "Double bed"},
            "price_nzd": 175.00,
            "pickup_date": "2026-11-01",
            "return_date": "2026-11-10"
        },
        {
            "model_name": "Ford Transit 4-Berth Motorhome",
            "berths": 4,
            "transmission": "Manual",
            "specs": {"solar": False, "battery": "200Ah", "heater": "Electric", "bed": "2 Double beds"},
            "price_nzd": 240.00,
            "pickup_date": "2026-11-01",
            "return_date": "2026-11-10"
        }
    ]
    
    print(f"成功解析到 {len(scraped_vehicles)} 款车型数据，开始写入数据库...")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        for v in scraped_vehicles:
            # 1. 写入或更新 van_models 表
            # 使用 ON CONFLICT 或先检查是否存在，保证幂等性
            cur.execute(
                """
                INSERT INTO van_models (model_name, berths, transmission, specs)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (v["model_name"], v["berths"], v["transmission"], psycopg2.extras.Json(v["specs"]) if "psycopg2.extras" else str(v["specs"]))
            )
            # 获取刚插入或已存在的 model_id
            # 简便起见，这里演示直接插入
            model_id = cur.fetchone()[0]

            # 2. 写入 pricing_inventory 表
            cur.execute(
                """
                INSERT INTO pricing_inventory (model_id, pickup_date, return_date, price_nzd, is_available)
                VALUES (%s, %s, %s, %s, TRUE);
                """,
                (model_id, v["pickup_date"], v["return_date"], v["price_nzd"])
            )
            
        conn.commit()
        print("🎉 结构化车型与价格数据已成功入库！")
        
    except Exception as e:
        conn.rollback()
        print(f"数据库写入出错: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    scrape_and_store_vehicles()