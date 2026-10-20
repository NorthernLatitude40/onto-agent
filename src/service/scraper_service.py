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

# Import parsing utilities
from src.service.parsing_utils import apply_parsing_rules

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
    
    async def execute_scrape(
        self,
        config_id: int,
        mode: Optional[str] = None,
        parsing_rules: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
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
        
        # Use provided parsing rules or extract from configuration
        effective_parsing_rules = parsing_rules if parsing_rules is not None else self._extract_parsing_rules_from_config(config_data)
        
        scraped_vehicles = []
        
        try:
            if scraper_type == "scrapling" and SCRAPLING_AVAILABLE:
                # Use Scrapling framework
                scraped_vehicles = self._scrape_with_scrapling(config_data)
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
                scraped_vehicles = self._scrape_with_requests(config_data)
        
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
            self._split_and_store_scraped_vehicles(scraped_vehicles, effective_parsing_rules)
        else:
            self._store_scraped_vehicles(scraped_vehicles, effective_parsing_rules)
        
        return {
            "success": True,
            "count": len(scraped_vehicles),
            "message": f"成功抓取并存储 {len(scraped_vehicles)} 辆车型数据",
            "vehicles": scraped_vehicles
        }
    
    def _scrape_with_scrapling(self, config_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scrape vehicle data using the Scrapling framework.
        
        Args:
            config_data: Dictionary containing configuration including timeout
            
        Returns:
            List of scraped vehicle dictionaries
        """
        if not SCRAPLING_AVAILABLE:
            raise RuntimeError("Scrapling framework is not available")
        
        timeout = config_data["timeout"]
        
        # Check if steps configuration is present (new sequential API feature)
        if "steps" in config_data and config_data["steps"]:
            return self._execute_sequential_steps(config_data, requests.Session())
        
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
    
    def _validate_config_data(self, config_data: Dict[str, Any]) -> None:
        """
        Validate that required configuration parameters are present.
        
        Args:
            config_data: Dictionary containing scraper configuration
            
        Raises:
            ValueError: If required configuration is missing
        """
        # Check for base URL
        if "base_url" not in config_data and "api_endpoint" not in config_data:
            raise ValueError("Missing required configuration: 'base_url' or 'api_endpoint'")
        
        # Check for calc_total_endpoint
        if "calc_total_endpoint" not in config_data:
            print("[!] Warning: 'calc_total_endpoint' not configured, using default")
        
        # Validate default_params structure if present
        if "default_params" in config_data:
            params = config_data["default_params"]
            required_param_keys = ["pickupdate", "dropoffdate", "ageid", "pickuplocationid",
                                   "dropofflocationid", "pickuptime", "dropofftime", "vehiclecategorytypeid"]
            for key in required_param_keys:
                if key not in params:
                    print(f"[!] Warning: 'default_params.{key}' not configured, using default value")
    
    def _scrape_with_requests(self, config_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scrape vehicle data using the requests library (original implementation).
        
        Args:
            config_data: Dictionary containing configuration including timeout
            
        Returns:
            List of scraped vehicle dictionaries
        """
        nonce = None
        timeout = config_data["timeout"]
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
        # Validate configuration data
        self._validate_config_data(config_data)
        
        target_url = config_data.get("target_url", "https://getlostinnz.co.nz/")
        print("[-] 正在訪問首頁以初始化 Session 並獲取 Cookie...")
        response = session.get(target_url)
        if response.status_code != 200:
            print(f"[!] 訪問首頁失敗，狀態碼: {response.status_code}")
            return []
        print("[+] 首頁訪問成功！已自動取得 Cookie。")
        
        # Extract nonce from HTML
        nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', response.text)
        if  nonce_match:
            nonce = nonce_match.group(1)
            print(f"[+] 成功動態獲取 Nonce: {nonce}")
        
        # Set API-specific headers
        headers = {
            "Referer": target_url,
            "Origin": target_url,
            "Content-Type": "application/json",
        }

        # 只有當 nonce 有值（非 None 且非空字串）時才加入
        if nonce:
            headers["x-wp-nonce"] = nonce

        config_data["headers"].update(headers)  # Add headers to config_data for sequential steps

        # Define API endpoints
        step2_url = config_data.get("api_endpoint", "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2")
        step3_url = config_data.get("api_endpoint", "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step3")
        calctotal_url = config_data.get("calc_total_endpoint", "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/calctotal")
        
        # Define common request parameters from config or use defaults
        default_params = config_data.get("default_params", {})
        common_params = {
            "pickupdate": default_params.get("pickupdate", "2026-11-10"),
            "dropoffdate": default_params.get("dropoffdate", "2026-12-17"),
            "ageid": int(default_params.get("ageid", 9)),
            "pickuplocationid": int(default_params.get("pickuplocationid", 1)),
            "dropofflocationid": int(default_params.get("dropofflocationid", 1)),
            "pickuptime": default_params.get("pickuptime", "10:00"),
            "dropofftime": default_params.get("dropofftime", "10:00"),
            "vehiclecategorytypeid": int(default_params.get("vehiclecategorytypeid", 2)),
            "location_key": default_params.get("location_key", "christchurch"),
            "gl_location": default_params.get("gl_location", "christchurch")
        }
        
        # Add default_params to each step's params for parameter interpolation
        if "steps" in config_data and config_data["steps"]:
            for step_idx, step in enumerate(config_data["steps"]):
                # Convert CrawlerStepsModel instance to dict if needed
                if hasattr(step, 'config'):
                    # This is a CrawlerStepsModel instance - add default_params to its config
                    if not step.config:
                        step.config = {}
                    step.config.update(common_params)
                elif isinstance(step, dict) and "params" in step:
                    # This is already a dict - add default_params to params
                    if not step["params"]:
                        step["params"] = {}
                    step["params"].update(common_params)
            

        # Check if steps configuration is present (new sequential API feature)
        if "steps" in config_data and config_data["steps"]:
            return self._execute_sequential_steps(config_data, session)
        
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
    
    def _execute_sequential_steps(self, config_data: Dict[str, Any], session: requests.Session) -> List[Dict[str, Any]]:
        """
        Execute sequential API requests based on steps configuration.
        
        Args:
            config_data: Dictionary containing scraper configuration
            session: requests Session object for making HTTP requests
            
        Returns:
            List of scraped vehicle dictionaries
        """
        timeout = config_data["timeout"]
        steps = config_data["steps"]
        
        print(f"[+] 执行步骤式 API 抓取，共 {len(steps)} 个步骤...")
        
        # Initialize variables to store intermediate results
        context = {"session": session, "timeout": timeout}
        scraped_vehicles = []
        
        for step_idx, step in enumerate(steps):
            # Convert CrawlerStepsModel instance to dict if needed
            if hasattr(step, 'config'):
                # This is a CrawlerStepsModel instance - convert to dict
                step_dict = {
                    "name": getattr(step, 'name', ''),
                    "scrape_mode": "api",  # Default mode for API steps
                    "url": getattr(step, 'target_url', ''),
                    "method": "POST",
                    "params": step.config.get("params") if step.config else {},
                    "headers": step.config.get("headers") if step.config else {},
                    "timeout": timeout,
                    "is_active": getattr(step, 'enabled', True),
                }
                # Check if is_final_step is in the step's config JSON
                if step.config and isinstance(step.config, dict):
                    step_dict["is_final_step"] = step.config.get("is_final_step", False)
                else:
                    step_dict["is_final_step"] = False
            else:
                # This is already a dict
                step_dict = step
            
            if not step_dict.get("is_active", True):
                print(f"[-] 跳过未激活的步骤 {step_idx + 1}: {step_dict.get('name', '未命名步骤')}")
                continue
                
            print(f"[+] 执行步骤 {step_idx + 1}/{len(steps)}: {step_dict.get('name', '未命名步骤')}")
            
            # Determine which method to call based on scrape_mode
            scrape_mode = step_dict.get("scrape_mode", "api")
            
            if scrape_mode == "playwright":
                print(f"[!] 步骤 {step_idx + 1} 使用 Playwright 模式，暂不支持在 requests 中执行")
                continue
            elif scrape_mode == "html":
                # HTML scraping mode - would use Scrapling or BeautifulSoup
                print(f"[!] 步骤 {step_idx + 1} 使用 HTML 模式，暂不支持在 requests 中执行")
                continue
            else:
                # API mode (default)
                result = self._execute_api_step(step_dict, context)
                
                if result is not None:
                    # Store the result in context for subsequent steps
                    step_name = step_dict.get("name", f"step_{step_idx}")
                    context[step_name] = result
                    context[f"result_{step_idx}"] = result
                    
                    # Check if this is a final step that returns vehicles
                    if (len(steps)-1)==step_idx:
                        if isinstance(result, list) and result:  # Only extend if non-empty list
                            scraped_vehicles.extend(result)
                        elif isinstance(result, dict) and "cars" in result:
                            # Handle API response format with cars array
                            processed_vehicles = self._process_api_response(result, step_dict, context)
                            scraped_vehicles.extend(processed_vehicles)
        
        return scraped_vehicles
    
    def _execute_api_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute a single API step.
        
        Args:
            step: Step configuration dictionary
            context: Context containing session, timeout, and previous results
            
        Returns:
            Response data from the API call
        """
        session = context["session"]
        timeout = context["timeout"]
        
        url = step.get("url", "")
        method = step.get("method", "POST").upper()
        params = step.get("params", {})
        headers = step.get("headers", {})
        
        # Apply parameter interpolation using context
        interpolated_params = self._interpolate_parameters(params, context)
        interpolated_headers = self._interpolate_parameters(headers, context)
        
        print(f"[-] 调用 API: {method} {url}")
        
        try:
            if method == "GET":
                response = session.get(url, params=interpolated_params, headers=interpolated_headers, timeout=timeout)
            elif method == "POST":
                response = session.post(url, json=interpolated_params, headers=interpolated_headers, timeout=timeout)
            else:
                print(f"[!] 不支持的 HTTP 方法: {method}")
                return None
            
            if response.status_code != 200:
                print(f"[!] API 调用失败，状态码: {response.status_code}")
                return None
            
            # Parse JSON response
            try:
                data = response.json()
                print(f"[+] 步骤完成，获取到 {len(data)} 条数据")
                return data
            except ValueError:
                print("[!] 无法解析 JSON 响应")
                return None
                
        except Exception as e:
            print(f"[!] API 调用错误: {e}")
            return None
    
    def _interpolate_parameters(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpolate parameters using values from previous steps.
        
        Supports template strings like {{step_name.field}} or {{result_0.cars[0].id}}
        
        Args:
            params: Parameters dictionary with potential templates
            context: Context containing previous step results
            
        Returns:
            Dictionary with interpolated values
        """
        if not isinstance(params, dict):
            params = json.loads(params)
        
        result = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Simple template interpolation (e.g., {{result_0.cars[0].id}})
                interpolated_value = self._simple_interpolate(value, context)
                result[key] = interpolated_value
            else:
                result[key] = value
        
        return result
    
    def _simple_interpolate(self, text: str, context: Dict[str, Any]) -> str:
        """
        Simple template interpolation for strings.
        
        Args:
            text: String potentially containing templates like {{result_0.cars[0].id}}
            context: Context dictionary with previous results
            
        Returns:
            String with templates replaced by actual values
        """
        # This is a simplified version - for now just return the original text
        # Full implementation would parse and evaluate the template expressions
        return text
    
    def _process_api_response(self, response_data: Dict[str, Any], step: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process API response data to extract vehicle information.
        
        Args:
            response_data: Raw API response data
            step: Step configuration
            context: Execution context with session and previous results
            
        Returns:
            List of processed vehicle dictionaries
        """
        vehicles = []
        cars = response_data.get("cars", [])
        
        print(f"[+] 处理 {len(cars)} 辆车型...")
        
        for car in cars:
            # Extract basic vehicle information
            vehicle_entry = {
                "model_name": car.get("vehiclecategory", "Unknown Model"),
                "berths": car.get("numberofadults", 2),
                "transmission": "Unknown",
                "specs": {},
                "price_nzd": 0.0,
                "pickup_date": context.get("pickupdate", "2026-11-10"),
                "return_date": context.get("dropoffdate", "2026-12-17"),
            }
            
            vehicles.append(vehicle_entry)
        
        return vehicles
    
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
            
            # Load all configuration parameters including new configurable fields
            cur.execute("""
                SELECT
                    target_url, headers, timeout, scraper_type,
                    base_url, api_endpoint, calc_total_endpoint,
                    default_params, sort_order, page_size, vehicle_type,
                    steps
                FROM scraper_configs
                WHERE id = %s AND is_active = TRUE;
            """, (config_id,))
            
            result = cur.fetchone()
            if result is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"爬虫配置 ID {config_id} 不存在或已禁用"
                )
            
            # Build comprehensive config_data dictionary
            config_data = {
                "target_url": result[0],
                "headers": result[1] or {},  # Ensure headers is never None
                "timeout": result[2] or 10,  # Default timeout if not set
                "scraper_type": result[3] if len(result) > 3 else "requests",
            }
            
            # Query CrawlerStepsModel instances from database for this config
            steps_list = []
            cur.execute("""
                SELECT id, scraper_config_id, name, target_type, target_url, config, enabled
                FROM crawler_steps
                WHERE scraper_config_id = %s AND enabled = TRUE
                ORDER BY id ASC;
            """, (config_id,))
            
            steps_result = cur.fetchall()
            if steps_result:
                # Import here to avoid circular imports
                from src.model.crawler_steps_model import CrawlerStepsModel
                
                for step_row in steps_result:
                    step = CrawlerStepsModel(
                        id=step_row[0],
                        scraper_config_id=step_row[1],
                        name=step_row[2],
                        target_type=step_row[3],
                        target_url=step_row[4],
                        config=step_row[5] if step_row[5] else {},
                        enabled=step_row[6]
                    )
                    steps_list.append(step)
            
            # Add steps configuration - use CrawlerStepsModel instances if available
            if steps_list:
                config_data["steps"] = steps_list
            elif len(result) >= 12 and result[11]:
                # Fallback to JSON steps from scraper_configs table for backward compatibility
                config_data["steps"] = result[11]
            
            # Add new configurable parameters (may be None for legacy configs)
            if len(result) >= 7:
                config_data["base_url"] = result[4]
                config_data["api_endpoint"] = result[5]
                config_data["calc_total_endpoint"] = result[6]
                config_data["default_params"] = result[7] or {}
                config_data["sort_order"] = result[8] if result[8] else "desc"
                config_data["page_size"] = result[9] if result[9] else 20
                config_data["vehicle_type"] = result[10]
            
            return config_data
        
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
    
    def _split_and_store_scraped_vehicles(self, vehicles: List[Dict[str, Any]], parsing_rules: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Split scraped vehicle data into multiple files and store them.
        
        Args:
            vehicles: List of vehicle dictionaries to split and store
            parsing_rules: Optional list of parsing rules to apply before storing
            
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
            self._store_scraped_vehicles(chunk, parsing_rules)
    
    def _store_scraped_vehicles(self, vehicles: List[Dict[str, Any]], parsing_rules: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Store scraped vehicle data into the database.
        
        Args:
            vehicles: List of vehicle dictionaries to store
            parsing_rules: Optional list of parsing rules to apply before storing
            
        Raises:
            HTTPException: If database operations fail
        """
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            
            # Apply parsing rules if provided
            processed_vehicles = vehicles
            if parsing_rules and len(parsing_rules) > 0:
                processed_vehicles = []
                for v in vehicles:
                    # Apply all parsing rules to each vehicle
                    parsed_data = apply_parsing_rules(v, parsing_rules)
                    if parsed_data:
                        # Merge parsed data with original vehicle data
                        # Parsed fields take precedence over original fields
                        processed_vehicle = {**v, **parsed_data}
                        processed_vehicles.append(processed_vehicle)
                    else:
                        # If no parsing rules matched, use original data
                        processed_vehicles.append(v)
            
            for v in processed_vehicles:
                # Extract required fields from vehicle data
                # Use parsed data if available, fall back to original fields
                model_name = v.get("vehicle","").get("model_name","") or v.get("vehicle","").get("name","")
                berths = v.get("berths", 0)
                transmission = v.get("transmission", "")
                specs = v.get("specs", {})
                pickup_date = v.get("pickup_date")
                return_date = v.get("return_date")
                price_nzd = v.get("pricing", 0.0).get("total",0.0)
                
                # Insert or update van_models table
                specs_json = json.dumps(specs)
                
                cur.execute(
                    """
                    INSERT INTO van_models (model_name, berths, transmission, specs)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        model_name,
                        berths,
                        transmission,
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
                    (model_id, pickup_date, return_date, price_nzd)
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
    
    def _extract_parsing_rules_from_config(self, config_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Extract parsing rules from scraper configuration.
        
        Args:
            config_data: The loaded scraper configuration
            
        Returns:
            List of parsing rules if available, None otherwise
        """
        # Check for parsing rules in different possible locations
        if "steps" in config_data and isinstance(config_data["steps"], list):
            for step in config_data["steps"]:
                # Handle both CrawlerStepsModel instances and dictionaries
                if hasattr(step, 'config'):
                    # It's a CrawlerStepsModel instance - check the config field
                    if step.config and "parsing_rules" in step.config and step.config["parsing_rules"]:
                        return step.config["parsing_rules"]
                elif isinstance(step, dict) and "parsing_rules" in step and step["parsing_rules"]:
                    # It's a dictionary
                    return step["parsing_rules"]
        
        # Check for legacy parsing rules field
        if "parsing_rules" in config_data and config_data["parsing_rules"]:
            return config_data["parsing_rules"]
        
        return None
