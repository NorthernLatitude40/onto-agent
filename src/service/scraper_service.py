"""
Vehicle Scraper Service
Provides business logic for vehicle data scraping operations
"""
import requests
import psycopg2
import os
import re
from dotenv import load_dotenv
import json
import random
import time
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

class ScraperService:
    """
    Service class for handling vehicle scraping operations.
    Encapsulates the business logic for executing scrape tasks.
    """
    
    def __init__(self):
        pass
    
    def execute_scrape(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        Execute a vehicle scraping task using the specified configuration.
        
        This method:
        1. Loads configuration from database
        2. Fetches vehicle data from target APIs
        3. Processes and stores the scraped data
        
        Args:
            config_id: The ID of the scraper configuration to use
            
        Returns:
            Dict containing scrape results with success status, count, message, and vehicles list
            
        Raises:
            HTTPException: If database operations or network requests fail
        """
        # Load configuration from database
        config_data = self._load_scraper_config(config_id)
        headers_data = config_data["headers"]
        timeout = config_data["timeout"]

        session = requests.Session()

        # 設定基本的模擬瀏覽器 Headers
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
                " like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        base_url = "https://getlostinnz.co.nz/"
        print("[-] 正在訪問首頁以初始化 Session 並獲取 Cookie...")
        response = session.get(base_url)
        if response.status_code != 200:
            print(f"[!] 訪問首頁失敗，狀態碼: {response.status_code}")
            return None
        print("[+] 首頁訪問成功！已自動取得 Cookie。")
        # 2. 動態從首頁的 HTML 原始碼中用正規表達式抓取最新的 Nonce
        nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', response.text)
        if nonce_match:
            nonce = nonce_match.group(1)
            print(f"[+] 成功動態獲取 Nonce: {nonce}")
        else:
            print("[!] 未能抓取到 Nonce，請檢查頁面結構是否變動")
            return
        
        # 3. 設定 API 專屬的 Headers（將動態抓到的 nonce 帶入，Cookie 則由 session 自動管理夾帶）
        headers = {
            "Referer": base_url,
            "Origin": "https://getlostinnz.co.nz",
            "Content-Type": "application/json",
            "x-wp-nonce": nonce,
        }
        
        # Define API endpoints from plans
        step2_url = "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2"
        step3_url = "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step3"
        calctotal_url = "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/calctotal"
        
        # Define common request parameters
        common_params = {
            "pickupdate": "2026-11-10",
            "dropoffdate": "2026-12-17",
            "ageid": 9,
            "pickuplocationid": 1,
            "dropofflocationid": 1,
            "pickuptime": "10:00",
            "dropofftime": "10:00",
            "vehiclecategorytypeid": 2,
            "location_key": "christchurch",
            "gl_location": "christchurch"
        }
        
        print(f"正在访问目标网站抓取车型数据...")
        
        # Add rate limiting with random delay between requests
        delay = random.uniform(1.0, 3.0)  # Random delay between 1 and 3 seconds
        print(f"等待 {delay:.2f} 秒以避免速率限制...")
        time.sleep(delay)
        
        scraped_vehicles = []
        
        try:
          # Call step2 API to get vehicle list
          step2_response = session.post(
              step2_url, json=common_params, headers=headers
          )
          step2_response.raise_for_status()
          vehicles_data = step2_response.json()

          # 【建議加上這行除錯】檢查 step2 回傳的完整結構長怎樣
          print("Step2 原始回應：", vehicles_data)

          # Call step3 API to get vehicle details and calctotal for price
          for vehicle in vehicles_data.get("cars", []):
            step3_params = common_params.copy()
            step3_params["vehiclecategoryid"] = vehicle.get(
                "vehiclecategoryid", 2
            )

            # 務必使用 session.post，才能延續前面取得的 Cookie 和 Session 狀態！
            step3_response = session.post(
                step3_url,
                json=step3_params,
                headers=headers,
                timeout=timeout,
            )
            step3_response.raise_for_status()
            vehicle_details = step3_response.json()

            # Call calctotal API to calculate price
            calctotal_params = {
                "pickupdate": common_params["pickupdate"],
                "pickuplocationid": common_params["pickuplocationid"],
                "vehiclecategoryid": vehicle.get("vehiclecategoryid", 2),
                "numberofdays": vehicle.get("numberofdays", 8),
                "totalrateafterdiscount": vehicle.get(
                    "totalrateafterdiscount", 1400
                ),
                "totalratebeforediscount": vehicle.get(
                    "totalratebeforediscount", 1400
                ),
                "freedaysamount": 0,
                "insuranceid": 0,
                "extrakmsid": 0,
                "optionalfeeamounts": [],
                "mandatoryfeeamounts": [49],
                "coupon": "",
                "campaigncode": "",
                "rental_discount": 0,
                "discount_name": "",
            }

            # 同樣改用 session.post
            calctotal_response = session.post(
                calctotal_url,
                json=calctotal_params,
                headers=headers,
                timeout=timeout,
            )
            calctotal_response.raise_for_status()
            price_data = calctotal_response.json()

            # Create vehicle entry
            specs = {
                "solar": vehicle_details.get("solar", False),
                "battery": vehicle_details.get("battery", "Unknown"),
                "heater": vehicle_details.get("heater", "Unknown"),
                "bed": vehicle_details.get("bed", "Unknown"),
            }

            vehicle_entry = {
                # 這裡將 "name" 改為 API 實際有的 "vehiclecategory"
                "model_name": vehicle.get("vehiclecategory", "Unknown Model"),
                # 如果沒有 berths，可以改用 numberofadults 或給預設值
                "berths": vehicle.get("numberofadults", 2),
                # 因為 API 沒給變速箱，若有需要可以從其他欄位補，或暫時給定/未知
                "transmission": "Unknown",
                "specs": specs,
                "price_nzd": price_data.get("trip_total", 0.0),
                "pickup_date": common_params["pickupdate"],
                "return_date": common_params["dropoffdate"],
            }

            scraped_vehicles.append(vehicle_entry)

        except Exception as api_error:
          print(f"API 调用错误: {api_error}")
          scraped_vehicles = []
        
        print(f"成功解析到 {len(scraped_vehicles)} 辆车型数据，开始写入数据库...")
        
        # Split data into multiple files if exceeding 400 rows
        if len(scraped_vehicles) > 400:
            self._split_and_store_scraped_vehicles(scraped_vehicles)
        else:
            self._store_scraped_vehicles(scraped_vehicles)
        
        return {
            "success": True,
            "count": len(scraped_vehicles),
            "message": f"成功抓取并存储 {len(scraped_vehicles)} 辆车型数据",
            "vehicles": scraped_vehicles
        }
    
    def _load_scraper_config(self, config_id: int) -> Dict[str, Any]:
        """
        Load scraper configuration from database.
        
        Args:
            config_id: The ID of the configuration to load
            
        Returns:
            Dictionary containing target_url, headers, and timeout
            
        Raises:
            HTTPException: If configuration not found or database error occurs
        """
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT target_url, headers, timeout
                FROM scraper_configs
                WHERE id = %s AND is_active = TRUE;
            """, (config_id,))
            
            result = cur.fetchone()
            if result is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"爬虫配置 ID {config_id} 不存在或已禁用"
                )
            
            return {
                "target_url": result[0],
                "headers": result[1],
                "timeout": result[2]
            }
        
        except Exception as e:
            print(f"数据库查询出错: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"数据库查询失败: {str(e)}"
            )
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
        
    def _split_and_store_scraped_vehicles(self, vehicles: List[Dict[str, Any]]) -> None:
        """
        Split scraped vehicle data into multiple files and store them.
        
        Args:
            vehicles: List of vehicle dictionaries to split and store
            
        Raises:
            HTTPException: If database operations fail
        """
        # Calculate number of chunks needed (400 rows per file)
        chunk_size = 400
        num_chunks = (len(vehicles) + chunk_size - 1) // chunk_size
        
        print(f"数据超过 400 行，将拆分为 {num_chunks} 个文件...")
        
        for i in range(num_chunks):
            start_idx = i * chunk_size
            end_idx = min(start_idx + chunk_size, len(vehicles))
            chunk = vehicles[start_idx:end_idx]
            
            print(f"处理分片 {i+1}/{num_chunks} (行 {start_idx+1}-{end_idx})...")
            self._store_scraped_vehicles(chunk)
    
    def _store_scraped_vehicles(self, vehicles: List[Dict[str, Any]]) -> None:
        """
        Store scraped vehicle data into the database.
        
        Args:
            vehicles: List of vehicle dictionaries to store
            
        Raises:
            HTTPException: If database operations fail
        """
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            for v in vehicles:
                # Insert or update van_models table
                specs_json = json.dumps(v["specs"])
                
                cur.execute(
                    """
                    INSERT INTO van_models (model_name, berths, transmission, specs)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        v["model_name"],
                        v["berths"],
                        v["transmission"],
                        specs_json
                    )
                )
                result = cur.fetchone()
                if result is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to get model_id after insertion"
                    )
                model_id = result[0]
                
                # Insert into pricing_inventory table
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
            if 'conn' in locals():
                conn.rollback()
            print(f"数据库写入出错: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"数据库操作失败: {str(e)}"
            )
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
        
