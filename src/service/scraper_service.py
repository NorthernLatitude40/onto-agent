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

# Import Scrapling framework
# Import Scrapling framework (optional)
try:
    from scrapling import Selector  # type: ignore
    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False
    print("Scrapling framework not available")

# Import Playwright scraper
from .playwright_scraper import PlaywrightScraper

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

class ScraperService:
    """
    Service class for handling vehicle scraping operations.
    Encapsulates the business logic for executing scrape tasks.
    
    Supports multiple scraping frameworks:
    - requests (default)
    - scrapling (if available)
    - playwright
    """
    
    def __init__(self):
        self.playwright_scraper = PlaywrightScraper()
    
    async def execute_scrape(self, config_id: int, mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a vehicle scraping task using the specified configuration.
        
        This method:
        1. Loads configuration from database
        2. Fetches vehicle data from target APIs
        3. Processes and stores the scraped data
        
        Args:
            config_id: The ID of the scraper configuration to use
            mode: Optional override for scraping mode (html/api/playwright)
            
        Returns:
            Dict containing scrape results with success status, count, message, and vehicles list
            
        Raises:
            HTTPException: If database operations or network requests fail
        """
        # Load configuration from database
        config_data = self._load_scraper_config(config_id)
        headers_data = config_data["headers"]
        timeout = config_data["timeout"]
        scraper_type = config_data.get("scraper_type", "requests")  # Default to requests

        scraped_vehicles = []
        
        try:
            if scraper_type == "scrapling" and SCRAPLING_AVAILABLE:
                # Use Scrapling framework
                scraped_vehicles = self._scrape_with_scrapling(timeout)
            elif scraper_type == "playwright":
                # Use Playwright scraper
                # Try using Scrapling framework if available, otherwise use execute_scrape
                scrape_result = await self.playwright_scraper.scrape_with_scrapling(config_data)
                if scrape_result and "vehicles" in scrape_result:
                    scraped_vehicles = scrape_result["vehicles"]
                else:
                    # Fallback to original execute_scrape method
                    scrape_result = await self.playwright_scraper.execute_scrape(config_data)
                    if scrape_result and "vehicles" in scrape_result:
                        scraped_vehicles = scrape_result["vehicles"]
                    else:
                        scraped_vehicles = []
            else:
                # Use requests (default)
                scraped_vehicles = self._scrape_with_requests(timeout)
        
        except Exception as api_error:
            print(f"API 调用错误: {api_error}")
            scraped_vehicles = []
        
        if not scraped_vehicles:
            return {
                "success": False,
                "count": 0,
                "message": "未能抓取到任何车型数据",
                "vehicles": []
            }
        
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
    
    def _scrape_with_scrapling(self, timeout: int) -> List[Dict[str, Any]]:
        """
        Scrape vehicle data using the Scrapling framework.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            List of scraped vehicle dictionaries
        """
        if not SCRAPLING_AVAILABLE:
            raise RuntimeError("Scrapling framework is not available")
        
        print("[+] 使用 Scrapling 框架进行数据抓取...")
        
        # Create a requests session for HTTP calls
        session = requests.Session()
        
        base_url = "https://getlostinnz.co.nz/"
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
        
        scraped_vehicles = []
        
        # Step 1: Get nonce from homepage
        print("[-] 正在訪問首頁以初始化 Session 並獲取 Cookie...")
        response = session.get(base_url, timeout=timeout)
        if response.status_code != 200:
            print(f"[!] 訪問首頁失敗，狀態碼: {response.status_code}")
            return []
        
        print("[+] 首頁訪問成功！已自動取得 Cookie。")
        
        # Extract nonce from page content
        nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', response.text)
        if not nonce_match:
            print("[!] 未能抓取到 Nonce，請檢查頁面結構是否變動")
            return []
        
        nonce = nonce_match.group(1)
        print(f"[+] 成功動態獲取 Nonce: {nonce}")
        
        # Set headers for API requests
        headers = {
            "Referer": base_url,
            "Origin": "https://getlostinnz.co.nz",
            "Content-Type": "application/json",
            "x-wp-nonce": nonce,
        }
        
        # Add rate limiting with random delay
        delay = random.uniform(1.0, 3.0)
        print(f"等待 {delay:.2f} 秒以避免速率限制...")
        time.sleep(delay)
        
        # Step 2: Get vehicle list
        print("正在访问目标网站抓取车型数据...")
        response = session.post(step2_url, json=common_params, headers=headers, timeout=timeout)
        if response.status_code != 200:
            print(f"[!] Step2 API 调用失败，状态码: {response.status_code}")
            return []
        
        vehicles_data = response.json()
        print("Step2 原始回應：", vehicles_data)
        
        # Step 3: Get vehicle details and prices
        for vehicle in vehicles_data.get("cars", []):
            step3_params = common_params.copy()
            step3_params["vehiclecategoryid"] = vehicle.get("vehiclecategoryid", 2)
            
            # Get vehicle details
            response = session.post(step3_url, json=step3_params, headers=headers, timeout=timeout)
            if response.status_code != 200:
                print(f"[!] Step3 API 调用失败，状态码: {response.status_code}")
                continue
            
            vehicle_details = response.json()
            
            # Calculate price
            calctotal_params = {
                "pickupdate": common_params["pickupdate"],
                "pickuplocationid": common_params["pickuplocationid"],
                "vehiclecategoryid": vehicle.get("vehiclecategoryid", 2),
                "numberofdays": vehicle.get("numberofdays", 8),
                "totalrateafterdiscount": vehicle.get("totalrateafterdiscount", 1400),
                "totalratebeforediscount": vehicle.get("totalratebeforediscount", 1400),
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
            
            response = session.post(calctotal_url, json=calctotal_params, headers=headers, timeout=timeout)
            if response.status_code != 200:
                print(f"[!] Calctotal API 调用失败，状态码: {response.status_code}")
                continue
            
            price_data = response.json()
            
            # Create vehicle entry
            specs = {
                "solar": vehicle_details.get("solar", False),
                "battery": vehicle_details.get("battery", "Unknown"),
                "heater": vehicle_details.get("heater", "Unknown"),
                "bed": vehicle_details.get("bed", "Unknown"),
            }
            
            vehicle_entry = {
                "model_name": vehicle.get("vehiclecategory", "Unknown Model"),
                "berths": vehicle.get("numberofadults", 2),
                "transmission": "Unknown",
                "specs": specs,
                "price_nzd": price_data.get("trip_total", 0.0),
                "pickup_date": common_params["pickupdate"],
                "return_date": common_params["dropoffdate"],
            }
            
            scraped_vehicles.append(vehicle_entry)
        
        return scraped_vehicles
    
    def _scrape_with_requests(self, timeout: int) -> List[Dict[str, Any]]:
        """
        Scrape vehicle data using the requests library (original implementation).
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            List of scraped vehicle dictionaries
        """
        print("[+] 使用 requests 库进行数据抓取...")
        
        session = requests.Session()
        
        # Set basic browser-like Headers
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
            return []
        print("[+] 首頁訪問成功！已自動取得 Cookie。")
        
        # Extract nonce from HTML
        nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', response.text)
        if not nonce_match:
            print("[!] 未能抓取到 Nonce，請檢查頁面結構是否變動")
            return []
        
        nonce = nonce_match.group(1)
        print(f"[+] 成功動態獲取 Nonce: {nonce}")
        
        # Set API-specific headers
        headers = {
            "Referer": base_url,
            "Origin": "https://getlostinnz.co.nz",
            "Content-Type": "application/json",
            "x-wp-nonce": nonce,
        }
        
        # Define API endpoints
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
        
        # Add rate limiting with random delay
        delay = random.uniform(1.0, 3.0)
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
            
            print("Step2 原始回應：", vehicles_data)
            
            # Call step3 API to get vehicle details and calctotal for price
            for vehicle in vehicles_data.get("cars", []):
                step3_params = common_params.copy()
                step3_params["vehiclecategoryid"] = vehicle.get(
                    "vehiclecategoryid", 2
                )
                
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
                    "model_name": vehicle.get("vehiclecategory", "Unknown Model"),
                    "berths": vehicle.get("numberofadults", 2),
                    "transmission": "Unknown",
                    "specs": specs,
                    "price_nzd": price_data.get("trip_total", 0.0),
                    "pickup_date": common_params["pickupdate"],
                    "return_date": common_params["dropoffdate"],
                }
                
                scraped_vehicles.append(vehicle_entry)
        
        except Exception as api_error:
            print(f"API 调用错误: {api_error}")
            return []
        
        return scraped_vehicles
    
    def _load_scraper_config(self, config_id: int) -> Dict[str, Any]:
        """
        Load scraper configuration from database.
        
        Args:
            config_id: The ID of the configuration to load
            
        Returns:
            Dictionary containing target_url, headers, timeout, and scraper_type
            
        Raises:
            HTTPException: If configuration not found or database error occurs
        """
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT target_url, headers, timeout, scraper_type
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
                "timeout": result[2],
                "scraper_type": result[3] if len(result) > 3 else "requests"
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
