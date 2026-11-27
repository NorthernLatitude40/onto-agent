"""
Vehicle Scraper Service
Provides business logic for vehicle data scraping operations
"""
import hashlib
import logging
import traceback
from datetime import datetime, timezone

import requests
import psycopg2
import os
import re

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None  # No-op if dotenv not available

import json
import random
import time
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from decimal import Decimal

# Import parsing utilities
from src.service.parsing_utils import (
    apply_parsing_rules,
    parse_html_with_rules,
    has_jsonpath_rules,
    is_jsonpath_rule,
    expand_parsed_result,
)

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

logger = logging.getLogger(__name__)

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
        self._current_config_id = None
        self._current_run_id = None

    async def execute_scrape(
        self,
        config_id: int,
        run_id: Optional[int] = None,
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
        # Record current config_id and run_id for use in storage methods
        self._current_config_id = config_id
        self._current_run_id = run_id
        
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
                    
                    if scrape_result and "html" in scrape_result:
                        # Handle HTML response from Playwright general scraping mode
                        html_content = scrape_result["html"]
                        print(f"[+] 从 Playwright 获取到 HTML 内容 ({len(html_content)} 字符)")
                        
                        # Apply parsing rules to extract structured data (JSON -> JSONPath, HTML -> CSS/XPath)
                        if effective_parsing_rules:
                            scraped_vehicles = self._parse_content_with_rules(
                                html_content, effective_parsing_rules, "Playwright"
                            )
                        else:
                            # No parsing rules - store raw HTML as text content
                            scraped_vehicles = [{"response_text": html_content}]
                    elif scrape_result and "vehicles" in scrape_result:
                        scraped_vehicles = scrape_result["vehicles"]
                    else:
                        scraped_vehicles = []
            else:
                # Use requests (default)
                scraped_vehicles = self._scrape_with_requests(config_data)
        
        except Exception as api_error:
            print(f"API 调用错误: {api_error}")
            traceback.print_exc()
            logger.error("[execute_scrape] 抓取失败 config_id=%s run_id=%s: %s", config_id, run_id, api_error, exc_info=True)
            scraped_vehicles = []
        
        if not scraped_vehicles:
            print(f"[!] 未解析到任何数据: config_id={config_id}, run_id={run_id}, 解析条数=0")
            return {
                "success": False,
                "count": 0,
                "message": "未能抓取到任何车型数据",
                "vehicles": []
            }
        
        print(f"成功抓取到 {len(scraped_vehicles)} 条数据项 (config_id={config_id}, run_id={run_id})，开始写入数据库...")
        
        # Split data into multiple chunks if exceeding 400 rows; config_id/run_id are passed explicitly
        if len(scraped_vehicles) > 400:
            stats = self._split_and_store_scraped_vehicles(scraped_vehicles, effective_parsing_rules, config_id, run_id)
        else:
            stats = self._store_scraped_vehicles(scraped_vehicles, effective_parsing_rules, config_id, run_id)
        
        print(
            f"[完成] config_id={config_id}, run_id={run_id}, 解析条数={len(scraped_vehicles)}, "
            f"scraped_items 写入 {stats.get('scraped_items', 0)} 条, 业务表写入 {stats.get('vehicles', 0)} 条"
        )
        
        return {
            "success": True,
            "count": len(scraped_vehicles),
            "message": f"成功抓取并存储 {len(scraped_vehicles)} 条数据项",
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
        print("正在访问目标网站抓取数据...")
        response = session.post(step2_url, json=common_params, headers=headers, timeout=timeout)
        
        # Log API response
        self._log_api_response("getlostinnz_step2", common_params, response.json(), response.status_code)
        
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
            
            # Log API response
            self._log_api_response("getlostinnz_step3", step3_params, response.json(), response.status_code)
            
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
            
            # Log API response
            self._log_api_response("getlostinnz_calctotal", calctotal_params, response.json(), response.status_code)
            
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
                "price_nzd": Decimal(price_data.get("trip_total", 0.0)),
                "pickup_date": common_params["pickupdate"],
                "return_date": common_params["dropoffdate"],
                "pickup_location": common_params.get("location_key", "christchurch"),
                "return_location": common_params.get("gl_location", "christchurch"),
                "start_time": common_params.get("pickuptime", "10:00"),
                "end_time": common_params.get("dropofftime", "10:00"),
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
        # Get parsing rules from config if not already extracted
        effective_parsing_rules = self._extract_parsing_rules_from_config(config_data)
        
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
        has_steps = bool(config_data.get("steps"))
        print("[-] 正在訪問首頁以初始化 Session 並獲取 Cookie...")
        response = session.get(target_url)
        home_ok = response.status_code == 200
        if not home_ok:
            logger.warning("[爬虫请求] 首页访问失败，状态码: %s", response.status_code)
            if not has_steps:
                return []
            # 配置了 steps：首页只是用来初始化 Session/Cookie/Nonce，失败也要继续执行后续步骤
            print(f"[!] 首页访问失败 (状态码 {response.status_code})，但配置了 steps，继续执行步骤...")
        else:
            print("[+] 首頁訪問成功！已自動取得 Cookie。")

        # 首页解析：仅当首页本身就是目标数据（例如直接返回 JSON API 数据）时才产出结果。
        # 带 steps 的配置，解析规则通常是针对步骤 API 的 JSONPath，首页(HTML)无法也不应套用，
        # 此时必须继续往下执行 _execute_sequential_steps，而不是 return [] 截断。
        if home_ok and effective_parsing_rules:
            home_items = self._parse_content_with_rules(response.text, effective_parsing_rules, "首页")
            if home_items:
                print(f"[+] 首页解析得到 {len(home_items)} 条数据，run_id={self._current_run_id}，将由 execute_scrape 统一写入")
                return home_items
            if has_steps:
                print("[-] 首页不是目标数据 / 解析结果为空，继续执行 steps 步骤式抓取...")
            else:
                print("[!] 首页解析结果为空，且未配置 steps，返回空结果")
                return []
        
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
        
        print(f"正在访问目标网站抓取数据...")
        
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
            
            # Log API response
            self._log_api_response("getlostinnz_step2", common_params, step2_response.json(), step2_response.status_code)
            
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
                
                # Log API response
                self._log_api_response("getlostinnz_step3", step3_params, step3_response.json(), step3_response.status_code)
                
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
                
                # Log API response
                self._log_api_response("getlostinnz_calctotal", calctotal_params, calctotal_response.json(), calctotal_response.status_code)
                
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
                    "price_nzd": Decimal(price_data.get("trip_total", 0.0)),
                    "pickup_date": common_params["pickupdate"],
                    "return_date": common_params["dropoffdate"],
                    "pickup_location": common_params.get("location_key", "christchurch"),
                    "return_location": common_params.get("gl_location", "christchurch"),
                    "start_time": common_params.get("pickuptime", "10:00"),
                    "end_time": common_params.get("dropofftime", "10:00"),
                }
                
                scraped_vehicles.append(vehicle_entry)
        
        except Exception as api_error:
            print(f"API 调用错误: {api_error}")
            traceback.print_exc()
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
            if hasattr(step, "config"):
                step_cfg = step.config if isinstance(step.config, dict) else {}
                step_dict = {
                    "name": getattr(step, "name", ""),
                    "scrape_mode": step_cfg.get("scrape_mode", "api"),
                    "url": getattr(step, "target_url", ""),
                    "method": step_cfg.get("method", "GET"),
                    "params": step_cfg.get("params") or {},
                    "headers": step_cfg.get("headers") or {},
                    "parsing_rules": step_cfg.get("parsing_rules"),
                    "timeout": timeout,
                    "is_active": getattr(step, "enabled", True),
                    "is_final_step": step_cfg.get("is_final_step", False),
                }
                # Check if is_final_step is in the step's config JSON
                if step.config and isinstance(step.config, dict):
                    step_dict["is_final_step"] = step.config.get("is_final_step", False)
                    # Preserve parsing_rules from step config
                    if "parsing_rules" in step.config:
                        step_dict["parsing_rules"] = step.config["parsing_rules"]
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
                    if step_dict.get("is_final_step") or (len(steps)-1)==step_idx:
                        if isinstance(result, list) and result:  # Only extend if non-empty list
                            scraped_vehicles.extend(result)
                        elif isinstance(result, dict):
                            # Handle both cars array format and other dict responses
                            if "cars" in result:
                                # Handle API response format with cars array
                                processed_vehicles = self._process_api_response(result, step_dict, context)
                                scraped_vehicles.extend(processed_vehicles)
                            else:
                                # For other dict responses (e.g., from non-JSON HTML parsing), convert to list
                                scraped_vehicles.append(result)
                else:
                    print(f"[!] 步骤 {step_idx + 1}/{len(steps)} ({step_dict.get('name', '未命名步骤')}) 未返回数据 (API 失败或解析为空)")
        
        print(f"[+] 步骤式抓取完成，共收集 {len(scraped_vehicles)} 条数据")
        return scraped_vehicles
    
    def _execute_api_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute a single API step.
        
        Args:
            step: Step configuration dictionary
            context: Context containing session, timeout, and previous results
            
        Returns:
            Response data from the API call (dict or list)
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

            # Check if response contains JSON data
            content_type = response.headers.get('Content-Type', '')
            is_json = 'application/json' in content_type.lower()
            
            # Log API response with safe JSON parsing
            step_name = step.get("name", "unknown_step")
            if is_json:
                json_data = response.json()
                self._log_api_response(step_name, interpolated_params, json_data, response.status_code)
            else:
                # For non-JSON responses, log the text content
                self._log_api_response(step_name, interpolated_params, {"response_text": response.text[:500]}, response.status_code)

            if response.status_code != 200:
                print(f"[!] API 调用失败，状态码: {response.status_code}")
                print("錯誤原因：", response.reason)
                print("伺服器返回的詳細錯誤內容：", response.text)
                return None

            step_name = step.get("name", "unknown_step")

            # Get parsing rules - check step first, then fall back to config-level rules
            parsing_rules = None
            if step.get("parsing_rules"):
                parsing_rules = step["parsing_rules"]
                print(f"[+] 使用步骤级解析规则: {len(parsing_rules)} 条规则")
            elif context.get("config_parsing_rules"):
                parsing_rules = context["config_parsing_rules"]
                print(f"[+] 使用配置级解析规则: {len(parsing_rules)} 条规则")

            if is_json:
                # json_data was parsed above (response.json() raises ValueError for invalid JSON,
                # which is handled by the outer except with a full traceback)
                if parsing_rules:
                    return self._parse_content_with_rules(json_data, parsing_rules, f"步骤[{step_name}]")

                # No parsing rules - return raw data
                if isinstance(json_data, list):
                    print(f"[+] 步骤完成，获取到 {len(json_data)} 条数据")
                    return json_data
                print("[+] 步骤完成，获取到单个对象")
                return [json_data]

            # Non-JSON content-type (e.g. HTML, or JSON served as text/html)
            html_content = response.text
            print(f"[+] 步骤完成，获取到文本响应 ({len(html_content)} 字符)")
            if parsing_rules:
                return self._parse_content_with_rules(html_content, parsing_rules, f"步骤[{step_name}]")

            # No parsing rules configured - wrap text in dictionary list format
            print(f"[+] 未配置解析规则，返回原始文本内容 ({len(html_content)} 字符)")
            return [{"response_text": html_content}]
        except Exception as e:
            print(f"[!] API 调用错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_content_with_rules(self, content: Any, rules: List[Dict[str, Any]], label: str = "") -> List[Dict[str, Any]]:
        """
        Parse a response body (JSON dict/list, JSON text, or HTML text) with parsing rules.

        - JSON + JSONPath rules  -> apply_parsing_rules(json_data, rules) (2 args), then expand
          per-field arrays into independent records
        - JSON + other rules     -> apply_parsing_rules(json_data, rules)
        - non-JSON (HTML) text   -> parse_html_with_rules, but ONLY with the non-JSONPath rules:
                                    JSONPath expressions must never be treated as CSS selectors

        Returns:
            List of record dicts (possibly empty). Never raises for "no data"; real errors propagate.
        """
        json_data = None
        is_json = False
        if isinstance(content, (dict, list)):
            json_data = content
            is_json = True
        elif isinstance(content, (str, bytes)):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, (dict, list)):
                    json_data = parsed
                    is_json = True
            except ValueError:
                pass  # Not JSON -> HTML parsing below

        jsonpath_present = has_jsonpath_rules(rules)

        if is_json:
            kind = "JSONPath" if jsonpath_present else "JSON"
            result = apply_parsing_rules(json_data, rules)
            items = expand_parsed_result(result)
            print(f"[+] {label} {kind} 解析完成，提取到 {len(items)} 条结构化数据")
            return items

        if jsonpath_present:
            html_rules = [r for r in rules if not is_jsonpath_rule(r)]
            if not html_rules:
                print(f"[-] {label} 响应不是 JSON，JSONPath 规则不适用，跳过解析 (不会当作 CSS 选择器)")
                return []
            print(f"[-] {label} 响应不是 JSON，忽略 {len(rules) - len(html_rules)} 条 JSONPath 规则，仅用 {len(html_rules)} 条 HTML 规则解析")
        else:
            html_rules = rules

        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        result = parse_html_with_rules(text, html_rules)
        items = result if isinstance(result, list) else ([result] if result else [])
        print(f"[+] {label} HTML 解析完成，提取到 {len(items)} 条结构化数据")
        return items

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
        import logging
        logger = logging.getLogger(__name__)
        
        vehicles = []
        
        # 检测响应内容类型 - JSON vs HTML
        has_cars_key = "cars" in response_data
        is_json_response = isinstance(response_data, dict) and (has_cars_key or len(response_data) > 0)
        
        if is_json_response:
            # JSON 响应：使用 cars 数组或整个响应数据
            cars = response_data.get("cars", [])
            data_to_parse = cars if isinstance(cars, list) and len(cars) > 0 else [response_data]
            
            logger.info(f"[API 响应处理] 检测到 JSON 响应，处理 {len(data_to_parse)} 个项目")
            
            for idx, car in enumerate(data_to_parse):
                try:
                    # 提取基本车辆信息
                    vehicle_entry = {
                        "model_name": car.get("vehiclecategory", "Unknown Model"),
                        "berths": car.get("numberofadults", 2),
                        "transmission": "Unknown",
                        "specs": {},
                        "price_nzd": Decimal('0.0'),
                        "pickup_date": context.get("pickupdate", "2026-11-10"),
                        "return_date": context.get("dropoffdate", "2026-12-17"),
                        "pickup_location": context.get("location_key", "christchurch"),
                        "return_location": context.get("gl_location", "christchurch"),
                        "start_time": context.get("pickuptime", "10:00"),
                        "end_time": context.get("dropofftime", "10:00"),
                    }
                    
                    vehicles.append(vehicle_entry)
                except Exception as e:
                    logger.error(f"[API 响应处理] 处理项目 {idx+1}/{len(data_to_parse)} 失败: {e}", exc_info=True)
            
            logger.info(f"[API 响应处理] JSON 完成。成功处理 {len(vehicles)}/{len(data_to_parse)} 个项目")
        else:
            # HTML 响应：使用现有逻辑
            cars = response_data.get("cars", [])
            
            logger.info(f"[API 响应处理] 检测到 HTML 响应，处理 {len(cars)} 辆车型...")
            
            for car in cars:
                # Extract basic vehicle information
                vehicle_entry = {
                    "model_name": car.get("vehiclecategory", "Unknown Model"),
                    "berths": car.get("numberofadults", 2),
                    "transmission": "Unknown",
                    "specs": {},
                    "price_nzd": Decimal('0.0'),
                    "pickup_date": context.get("pickupdate", "2026-11-10"),
                    "return_date": context.get("dropoffdate", "2026-12-17"),
                    "pickup_location": context.get("location_key", "christchurch"),
                    "return_location": context.get("gl_location", "christchurch"),
                    "start_time": context.get("pickuptime", "10:00"),
                    "end_time": context.get("dropofftime", "10:00"),
                }
                
                vehicles.append(vehicle_entry)
            
            logger.info(f"[API 响应处理] HTML 完成。成功处理 {len(vehicles)} 辆车型")
        
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
        
        except HTTPException:
            raise
        except Exception as e:
            print(f"数据库查询出错: {e}")
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"数据库查询失败: {str(e)}"
            )
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    
    def _split_and_store_scraped_vehicles(
        self,
        vehicles: List[Dict[str, Any]],
        parsing_rules: Optional[List[Dict[str, Any]]] = None,
        config_id: Optional[int] = None,
        run_id: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Split scraped vehicle data into chunks and store them.

        Args:
            vehicles: List of vehicle dictionaries to split and store
            parsing_rules: Optional list of parsing rules to apply before storing
            config_id: Optional config_id override for storage methods
            run_id: Optional run_id override for storage methods

        Returns:
            Aggregated {"vehicles": n, "scraped_items": m} across all chunks

        Raises:
            HTTPException: If database operations fail
        """
        # Calculate number of chunks needed (400 rows per file)
        chunk_size = 400
        num_chunks = (len(vehicles) + chunk_size - 1) // chunk_size

        print(f"数据超过 400 行，将拆分为 {num_chunks} 个文件...")

        total = {"vehicles": 0, "scraped_items": 0}
        for i in range(num_chunks):
            start_idx = i * chunk_size
            end_idx = min(start_idx + chunk_size, len(vehicles))
            chunk = vehicles[start_idx:end_idx]

            print(f"处理分片 {i+1}/{num_chunks} (行 {start_idx+1}-{end_idx})...")
            stats = self._store_scraped_vehicles(chunk, parsing_rules, config_id, run_id)
            total["vehicles"] += stats.get("vehicles", 0)
            total["scraped_items"] += stats.get("scraped_items", 0)
        return total


    def _log_api_response(
        self,
        api_name: str,
        request_payload: Optional[Dict[str, Any]],
        response_data: Dict[str, Any],
        status_code: int
    ) -> None:
        """
        Log API responses to the api_logs table.

        Args:
            api_name: Name of the API or vendor being called
            request_payload: Request parameters sent (optional)
            response_data: Complete raw JSON response from API
            status_code: HTTP status code
        """
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # Convert request_payload to JSON string if provided, otherwise NULL
            request_json = json.dumps(request_payload) if request_payload else None
            response_json = json.dumps(response_data)

            cur.execute(
                """
                INSERT INTO api_logs (api_name, request_payload, response_data, status_code)
                VALUES (%s, %s, %s, %s);
                """,
                (
                    api_name,
                    request_json,
                    response_json,
                    status_code
                )
            )

            conn.commit()
        except Exception as e:
            print(f"[!] 记录 API 日志失败: {e}")
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

    def _store_scraped_vehicles(
        self,
        vehicles: List[Dict[str, Any]],
        parsing_rules: Optional[List[Dict[str, Any]]] = None,
        config_id: Optional[int] = None,
        run_id: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Store scraped vehicle data into the database.

        Rental-vehicle records go to van_models / pricing_inventory (unchanged);
        every other record goes to scraped_items.

        Args:
            vehicles: List of vehicle dictionaries to store
            parsing_rules: Optional list of parsing rules to apply before storing
            config_id: Optional config_id override for storage methods
            run_id: Optional run_id override for storage methods

        Returns:
            {"vehicles": <rows written to business tables>, "scraped_items": <rows written to scraped_items>}

        Raises:
            HTTPException: If database operations fail
        """
        effective_config_id = config_id if config_id is not None else self._current_config_id
        effective_run_id = run_id if run_id is not None else self._current_run_id
        business_count = 0
        items_count = 0

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # Apply parsing rules if provided
            processed_vehicles = []
            vehicle_count = len(vehicles)

            logger.info(
                "[存储车辆] 开始处理 %s 条数据, config_id=%s, run_id=%s",
                vehicle_count, effective_config_id, effective_run_id
            )

            if parsing_rules and len(parsing_rules) > 0:
                for idx, v in enumerate(vehicles):
                    try:
                        # Apply all parsing rules to each vehicle
                        parsed_data = apply_parsing_rules(v, parsing_rules)
                        # apply_parsing_rules fills unmatched fields with None, so a dict whose values are
                        # all None means "nothing matched" (e.g. v is already parsed): keep the original data.
                        if parsed_data and any(val is not None for val in parsed_data.values()):
                            processed_vehicles.append(parsed_data)
                        else:
                            processed_vehicles.append(v)
                    except Exception as e:
                        logger.error(f"[存储车辆] 处理项目 {idx+1}/{vehicle_count} 失败: {e}", exc_info=True)
                        traceback.print_exc()
            else:
                # When no parsing rules provided, use vehicles as-is
                processed_vehicles = vehicles

            items_for_scraped_table: List[Dict[str, Any]] = []

            for v in processed_vehicles:
                # Check if this record belongs to rental vehicle structure
                has_model_name = "model_name" in v and bool(v.get("model_name"))
                has_rental_fields = any(
                    field in v and bool(v.get(field))
                    for field in ["berths", "transmission", "price_nzd"]
                )

                # If not a rental vehicle record, store as scraped item instead
                if not has_model_name or (not has_rental_fields):
                    items_for_scraped_table.append(v)
                    continue
                cur.execute(
                    """
                    INSERT INTO van_models (model_name, berths, transmission, specs)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        v.get("model_name"),
                        v.get("berths"),
                        v.get("transmission"),
                        v.get("specs")
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
                    INSERT INTO pricing_inventory
                    (model_id, price_nzd, is_available, pickup_location, return_location,
                     start_time, end_time)
                    VALUES (%s, %s, TRUE, %s, %s, %s, %s);
                    """,
                    (model_id, v.get("price_nzd"),
                     v.get("pickup_location"), v.get("return_location"), v.get("start_time"), v.get("end_time"))
                )
                business_count += 1
                
                # Add to scraped_items table as well (dual-write for rental items)
                items_for_scraped_table.append(v)

            if items_for_scraped_table:
                items_count = self._store_scraped_items(
                    items_for_scraped_table,
                    config_id=effective_config_id,
                    run_id=effective_run_id,
                    step_name=None
                )

            conn.commit()

            summary = (
                f"[存储汇总] config_id={effective_config_id}, run_id={effective_run_id}, "
                f"输入 {vehicle_count} 条, 业务表(van_models/pricing_inventory)写入 {business_count} 条, "
                f"scraped_items 写入 {items_count} 条 (待写入 {len(items_for_scraped_table)} 条)"
            )
            logger.info(summary)
            print(summary)
            print("🎉 结构化数据已成功入库！")
            return {"vehicles": business_count, "scraped_items": items_count}

        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            logger.error(
                "[存储车辆] 数据库写入出错 config_id=%s run_id=%s: %s",
                effective_config_id, effective_run_id, e, exc_info=True
            )
            print(f"数据库写入出错 (config_id={effective_config_id}, run_id={effective_run_id}): {e}")
            traceback.print_exc()
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"数据库操作失败: {str(e)}"
            )
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()


    def _build_dedup_key(
        self,
        config_id: Optional[int],
        step_name: Optional[str],
        source_url: Optional[str],
        title: str,
        canonical_data: str,
    ) -> str:
        """
        Build a stable dedup_key for a scraped item.

        Format: "<config_id>:<step_name or ->:<sha1>", where sha1 is computed over
        source_url + title + canonical (sorted-keys) JSON of the item. The key is
        config-scoped, deterministic across runs (same content => same key), distinct for
        different items even when title is empty, and always short enough for varchar columns.
        """
        digest = hashlib.sha1(
            "||".join([source_url or "", title or "", canonical_data]).encode("utf-8")
        ).hexdigest()
        return f"{config_id if config_id is not None else '-'}:{step_name or '-'}:{digest}"

    def _store_scraped_items(
        self,
        items: List[Dict[str, Any]],
        config_id: Optional[int] = None,
        run_id: Optional[int] = None,
        step_name: Optional[str] = None,
        source_url: Optional[str] = None
    ) -> int:
        """
        Store scraped items into the scraped_items table (no foreign keys).

        Args:
            items: List of item dictionaries to store
            config_id: The scraper configuration ID (falls back to self._current_config_id)
            run_id: The scrape run ID (falls back to self._current_run_id)
            step_name: Optional name of the scraping step
            source_url: Optional URL where data was scraped from (falls back to item["source_url"])

        Returns:
            Number of rows actually inserted (rows skipped by dedup_key conflict are not counted)

        Raises:
            HTTPException: If database operations fail
        """
        effective_config_id = config_id if config_id is not None else self._current_config_id
        effective_run_id = run_id if run_id is not None else self._current_run_id

        if not items:
            print(f"📦 scraped_items: 无数据可写入 (config_id={effective_config_id}, run_id={effective_run_id})")
            return 0

        inserted = 0
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            for item in items:
                if not isinstance(item, dict):
                    item = {"value": item}

                # Extract title from item (use a common field or create a summary)
                title = item.get("title") or ""
                if not title and item.get("model_name"):
                    title = item.get("model_name")
                title = str(title) if title else ""

                item_source_url = source_url or item.get("source_url")
                if item_source_url is not None:
                    item_source_url = str(item_source_url)

                # Convert Decimal objects etc. to strings for JSON serialization
                item_data = json.loads(json.dumps(item, default=str))
                data_json = json.dumps(item_data, ensure_ascii=False)
                canonical = json.dumps(item_data, sort_keys=True, ensure_ascii=False)

                dedup_key = self._build_dedup_key(
                    effective_config_id, step_name, item_source_url, title, canonical
                )

                # ON CONFLICT DO NOTHING: safe whether or not a unique index exists on dedup_key
                cur.execute(
                    """
                    INSERT INTO scraped_items (config_id, run_id, step_name, source_url, title, data, dedup_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (
                        effective_config_id,
                        effective_run_id,
                        step_name,
                        item_source_url,
                        title,
                        data_json,
                        dedup_key
                    )
                )
                if cur.rowcount and cur.rowcount > 0:
                    inserted += cur.rowcount

            conn.commit()
            skipped = len(items) - inserted
            msg = (
                f"scraped_items 写入完成: config_id={effective_config_id}, run_id={effective_run_id}, "
                f"step_name={step_name}, 待写入 {len(items)} 条, 实际写入 {inserted} 条, 重复跳过 {skipped} 条"
            )
            logger.info(msg)
            print(f"📦 {msg}")
            return inserted

        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            logger.error(
                "[scraped_items] 数据库写入出错 config_id=%s run_id=%s: %s",
                effective_config_id, effective_run_id, e, exc_info=True
            )
            print(f"数据库写入出错 (scraped_items, config_id={effective_config_id}, run_id={effective_run_id}): {e}")
            traceback.print_exc()
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
                elif isinstance(step, dict):
                    # Handle dictionary format - check both direct parsing_rules and config.parsing_rules
                    if "parsing_rules" in step and step["parsing_rules"]:
                        return step["parsing_rules"]
                    elif "config" in step and isinstance(step["config"], dict):
                        # Check nested config field
                        if "parsing_rules" in step["config"] and step["config"]["parsing_rules"]:
                            return step["config"]["parsing_rules"]
        
        # Check for legacy parsing rules field
        if "parsing_rules" in config_data and config_data["parsing_rules"]:
            return config_data["parsing_rules"]
        
        return None