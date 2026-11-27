"""
Playwright-based Scraper Service
Provides browser automation for vehicle data scraping operations
"""
import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page
from typing import List, Dict, Any, Optional
import json
import time
import random
from bs4 import BeautifulSoup

# Import Scrapling framework (optional)
try:
    from scrapling import Selector  # type: ignore
    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False
    print("Scrapling framework not available")


class PlaywrightScraper:
    """
    Service class for handling vehicle scraping operations using Playwright.
    Encapsulates the business logic for executing scrape tasks with browser automation.
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        """Async context manager entry point"""
        self.playwright = await async_playwright().start()
        # Launch browser with headless mode based on environment
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point"""
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def execute_scrape(self, config_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute a scraping task using Playwright browser automation.

        This method:
        1. Launches a browser context with proper headers
        2. Navigates to the target website
        3. For rental car sites: extracts vehicle data using browser automation and API calls
        4. For general scraping: returns the HTML content for parsing
        5. Processes and returns the scraped data

        Args:
            config_data: Dictionary containing scraper configuration
                - target_url: Base URL of the website
                - headers: HTTP headers as dict
                - timeout: Request timeout in seconds
                - common_params: Common request parameters (for rental sites)
                - step2_url, step3_url, calctotal_url: API endpoints (for rental sites)
                - scrape_mode: "rental" or "general" to determine scraping approach

        Returns:
            Dict containing scrape results with success status, count, message, and vehicles list
        """
        try:
            # Create a new browser context for each scrape to ensure clean state
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            self.page = await self.context.new_page()

            base_url = config_data.get("target_url", "https://getlostinnz.co.nz/")
            timeout = config_data.get("timeout", 10)
            scrape_mode = config_data.get("scrape_mode", "rental")

            print(f"[Playwright] 正在访问目标网站: {base_url}")
            print(f"[Playwright] 抓取模式: {scrape_mode}")

            # Navigate to the base URL
            await self.page.goto(base_url, timeout=timeout * 1000)

            # For general scraping mode, just return the HTML content
            if scrape_mode == "general":
                html_content = await self.page.content()
                print(f"[Playwright] 成功获取页面 HTML 内容 ({len(html_content)} 字节)")
                return {
                    "success": True,
                    "count": 1,
                    "message": "General scraping completed",
                    "html": html_content
                }

            # For rental car sites, extract nonce and call APIs
            # Set up common parameters with fallbacks (rental-specific)
            if config_data.get("common_params"):
                common_params = config_data["common_params"]
            else:
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

            # Use configurable API endpoints from config, fallback to defaults (rental-specific)
            step2_url = config_data.get(
                "step2_url",
                "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2"
            )
            step3_url = config_data.get(
                "step3_url",
                "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step3"
            )
            calctotal_url = config_data.get(
                "calctotal_url",
                "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/calctotal"
            )

            # Extract nonce from page content using Playwright (rental-specific)
            nonce = await self._extract_nonce_from_page()
            if not nonce:
                print("[Playwright] 未能抓取到 Nonce，请检查页面结构是否变动")
                return None
            
            print(f"[Playwright] 成功获取 Nonce: {nonce}")
            
            # Add rate limiting with random delay between requests
            delay = random.uniform(1.0, 3.0)
            print(f"[Playwright] 等待 {delay:.2f} 秒以避免速率限制...")
            time.sleep(delay)

            scraped_vehicles = []

            # For rental car sites, call APIs to get vehicle data
            if scrape_mode == "rental":
                scraped_vehicles = []
                
                # Call step2 API to get vehicle list
            step2_response = await self._call_api_with_playwright(
                step2_url,
                common_params,
                nonce
            )
            
            if not step2_response or "cars" not in step2_response:
                print(f"[Playwright] Step2 API 返回无效数据: {step2_response}")
                return {
                    "success": False,
                    "count": 0,
                    "message": "Step2 API 返回无效数据",
                    "vehicles": []
                }

            print(f"[Playwright] Step2 原始回应: {step2_response}")

            # Call step3 and calctotal APIs for each vehicle
            for vehicle in step2_response.get("cars", []):
                step3_params = common_params.copy()
                step3_params["vehiclecategoryid"] = vehicle.get("vehiclecategoryid", 2)

                # Call step3 API to get vehicle details
                step3_response = await self._call_api_with_playwright(
                    step3_url,
                    step3_params,
                    nonce
                )
                
                if not step3_response:
                    continue

                # Call calctotal API to calculate price
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

                calctotal_response = await self._call_api_with_playwright(
                    calctotal_url,
                    calctotal_params,
                    nonce
                )
                
                if not calctotal_response:
                    continue

                # Create vehicle entry
                specs = {
                    "solar": step3_response.get("solar", False),
                    "battery": step3_response.get("battery", "Unknown"),
                    "heater": step3_response.get("heater", "Unknown"),
                    "bed": step3_response.get("bed", "Unknown"),
                }

                vehicle_entry = {
                    "model_name": vehicle.get("vehiclecategory", "Unknown Model"),
                    "berths": vehicle.get("numberofadults", 2),
                    "transmission": "Unknown",
                    "specs": specs,
                    "price_nzd": calctotal_response.get("trip_total", 0.0),
                    "pickup_date": common_params["pickupdate"],
                    "return_date": common_params["dropoffdate"],
                }

                scraped_vehicles.append(vehicle_entry)

                print(f"[Playwright] 成功解析到 {len(scraped_vehicles)} 辆车型数据")
            else:
                # For general scraping, we already returned HTML above
                # This should not be reached for scrape_mode == "general"
                return {
                    "success": False,
                    "count": 0,
                    "message": "Invalid scrape mode",
                    "vehicles": []
                }

            return {
                "success": True,
                "count": len(scraped_vehicles),
                "message": f"使用 Playwright 成功抓取并处理 {len(scraped_vehicles)} 辆车型数据",
                "vehicles": scraped_vehicles
            }

        except Exception as e:
            print(f"[Playwright] 执行错误: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "count": 0,
                "message": f"Playwright 执行错误: {str(e)}",
                "vehicles": []
            }
        finally:
            # Clean up resources
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None


    async def _extract_nonce_from_page_with_scrapling(
        self, page: Page
    ) -> Optional[str]:
        """
        Extract nonce from page content using Scrapling.

        Args:
            page: Scrapling Page object

        Returns:
            The extracted nonce string, or None if not found
        """
        try:
            # Get page content
            content = await page.content()

            # Use BeautifulSoup to parse and extract nonce
            soup = BeautifulSoup(content, 'html.parser')

            # Try to find nonce in script tags or meta tags
            # Looking for pattern: "nonce":"[a-f0-9]+"
            import re
            nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', content)

            if nonce_match:
                return nonce_match.group(1)

            # Alternative: Look in data attributes or other common locations
            for script in soup.find_all('script'):
                if 'nonce' in str(script):
                    nonce_match = re.search(r'nonce["\s:]+([a-f0-9]+)', str(script))
                    if nonce_match:
                        return nonce_match.group(1)

            return None
        except Exception as e:
            print(f"[Scrapling] 提取 nonce 时出错: {e}")
            return None

    async def _call_api_with_scrapling(
        self,
        page: Page,
        url: str,
        params: Dict[str, Any],
        nonce: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call API endpoint using Scrapling's request capabilities.

        Args:
            page: Scrapling Page object
            url: API endpoint URL
            params: Request parameters as dict
            nonce: Security nonce for authentication

        Returns:
            Parsed JSON response as dict, or None if request failed
        """
        try:
            # Set up headers with nonce
            await page.evaluate("() => {}")  # Ensure page is ready

            # Make POST request using Scrapling's fetch API
            response = await page.request.post(
                url,
                data=json.dumps(params),
                headers={
                    "Content-Type": "application/json",
                    "X-Nonce": nonce
                }
            )

            if not response.ok:
                print(f"[Scrapling] API 请求失败: {response.status}")
                return None

            # Parse JSON response
            json_response = await response.json()
            return json_response

        except Exception as e:
            print(f"[Scrapling] 调用 API 时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _extract_nonce_from_page(self) -> Optional[str]:
        """
        Extract nonce from page content using Playwright.

        Returns:
            The extracted nonce string, or None if not found
        """
        try:
            # Get page content
            content = await self.page.content()
            
            # Use BeautifulSoup to parse and extract nonce
            soup = BeautifulSoup(content, 'html.parser')
            
            # Try to find nonce in script tags or meta tags
            # Looking for pattern: "nonce":"[a-f0-9]+"
            import re
            nonce_match = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', content)
            
            if nonce_match:
                return nonce_match.group(1)
            
            # Alternative: Look in data attributes or other common locations
            for script in soup.find_all('script'):
                if 'nonce' in str(script):
                    nonce_match = re.search(r'nonce["\s:]+([a-f0-9]+)', str(script))
                    if nonce_match:
                        return nonce_match.group(1)
            
            return None
        except Exception as e:
            print(f"[Playwright] 提取 nonce 时出错: {e}")
            return None

    async def _call_api_with_playwright(
        self,
        url: str,
        params: Dict[str, Any],
        nonce: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call API endpoint using Playwright's request capabilities.

        Args:
            url: API endpoint URL
            params: Request parameters as dict
            nonce: Security nonce for authentication

        Returns:
            Parsed JSON response as dict, or None if request failed
        """
        try:
            # Set up headers with nonce
            await self.page.evaluate("() => {}")  # Ensure page is ready
            
            # Make POST request using fetch API through Playwright
            response = await self.page.request.post(
                url,
                data=json.dumps(params),
                headers={
                    "Content-Type": "application/json",
                    "x-wp-nonce": nonce,
                    "Referer": "https://getlostinnz.co.nz/",
                    "Origin": "https://getlostinnz.co.nz"
                }
            )
            
            if response.status != 200:
                print(f"[Playwright] API 调用失败，状态码: {response.status}")
                return None
            
            # Get response body as text and parse JSON
            response_text = await response.text()
            return json.loads(response_text)
            
        except Exception as e:
            print(f"[Playwright] API 调用错误: {e}")
            return None

    async def scrape_with_playwright(self, config_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Alternative implementation using Playwright's page.evaluate for JavaScript execution.

        Args:
            config_data: Dictionary containing scraper configuration

        Returns:
            Dict containing scrape results with success status, count, message, and vehicles list
        """
        try:
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            self.page = await self.context.new_page()

            base_url = config_data.get("target_url", "https://getlostinnz.co.nz/")
            timeout = config_data.get("timeout", 10)

            # Set up common parameters with fallbacks
            if config_data.get("common_params"):
                common_params = config_data["common_params"]
            else:
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

            print(f"[Playwright] 正在访问目标网站: {base_url}")
            
            # Navigate to the base URL
            await self.page.goto(base_url, timeout=timeout * 1000)
            
            # Extract nonce using JavaScript evaluation (only for rental mode)
            scrape_mode = config_data.get("scrape_mode", "rental")
            nonce = None
            if scrape_mode == "rental":
                nonce = await self._extract_nonce_with_js()
                if not nonce:
                    print("[Playwright] 未能抓取到 Nonce，请检查页面结构是否变动")
                    return None
            
            print(f"[Playwright] 成功获取 Nonce: {nonce}")
            
            # Add rate limiting with random delay between requests
            delay = random.uniform(1.0, 3.0)
            print(f"[Playwright] 等待 {delay:.2f} 秒以避免速率限制...")
            time.sleep(delay)

            scraped_vehicles = []

            # For general or playwright scraping mode, return HTML content instead of calling APIs
            scrape_mode = config_data.get("scrape_mode", "rental")
            if scrape_mode in ["general", "playwright"]:
                html_content = await self.page.content()
                print(f"[Playwright] 成功获取页面 HTML 内容 ({len(html_content)} 字节)")
                return {
                    "success": True,
                    "count": 1,
                    "message": "General scraping completed",
                    "html": html_content
                }

            # Call step2 API to get vehicle list (rental mode only)
            step2_url = config_data.get(
                "step2_url",
                "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2"
            )
            
            step2_response = await self._call_api_with_js(
                step2_url,
                common_params,
                nonce
            )
            
            if not step2_response or "cars" not in step2_response:
                print(f"[Playwright] Step2 API 返回无效数据: {step2_response}")
                return {
                    "success": False,
                    "count": 0,
                    "message": "Step2 API 返回无效数据",
                    "vehicles": []
                }

            print(f"[Playwright] Step2 原始回应: {step2_response}")

            # Call step3 and calctotal APIs for each vehicle
            for vehicle in step2_response.get("cars", []):
                step3_params = common_params.copy()
                step3_params["vehiclecategoryid"] = vehicle.get("vehiclecategoryid", 2)

                # Call step3 API to get vehicle details
                step3_url = config_data.get(
                    "step3_url",
                    "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step3"
                )
                
                step3_response = await self._call_api_with_js(
                    step3_url,
                    step3_params,
                    nonce
                )
                
                if not step3_response:
                    continue

                # Call calctotal API to calculate price
                calctotal_url = config_data.get(
                    "calctotal_url",
                    "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/calctotal"
                )
                
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

                calctotal_response = await self._call_api_with_js(
                    calctotal_url,
                    calctotal_params,
                    nonce
                )
                
                if not calctotal_response:
                    continue

                # Create vehicle entry
                specs = {
                    "solar": step3_response.get("solar", False),
                    "battery": step3_response.get("battery", "Unknown"),
                    "heater": step3_response.get("heater", "Unknown"),
                    "bed": step3_response.get("bed", "Unknown"),
                }

                vehicle_entry = {
                    "model_name": vehicle.get("vehiclecategory", "Unknown Model"),
                    "berths": vehicle.get("numberofadults", 2),
                    "transmission": "Unknown",
                    "specs": specs,
                    "price_nzd": calctotal_response.get("trip_total", 0.0),
                    "pickup_date": common_params["pickupdate"],
                    "return_date": common_params["dropoffdate"],
                }

                scraped_vehicles.append(vehicle_entry)

            print(f"[Playwright] 成功解析到 {len(scraped_vehicles)} 辆车型数据")

            return {
                "success": True,
                "count": len(scraped_vehicles),
                "message": f"使用 Playwright 成功抓取并处理 {len(scraped_vehicles)} 辆车型数据",
                "vehicles": scraped_vehicles
            }

        except Exception as e:
            print(f"[Playwright] 执行错误: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "count": 0,
                "message": f"Playwright 执行错误: {str(e)}",
                "vehicles": []
            }
        finally:
            # Clean up resources
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None

    async def _extract_nonce_with_js(self) -> Optional[str]:
        """
        Extract nonce from page using JavaScript evaluation.

        Returns:
            The extracted nonce string, or None if not found
        """
        try:
            # Use JavaScript to extract nonce from the page
            nonce = await self.page.evaluate(r"""
                () => {
                    // Try to find nonce in various common locations
                    const scripts = document.getElementsByTagName('script');
                    for (let script of scripts) {
                        const content = script.textContent || '';
                        const match = content.match(/\"nonce\"\s*:\s*\"([a-f0-9]+)\"/);
                        if (match && match[1]) {
                            return match[1];
                        }
                    }
                    
                    // Try to find in data attributes
                    const elements = document.querySelectorAll('[data-nonce]');
                    for (let el of elements) {
                        const nonce = el.getAttribute('data-nonce');
                        if (nonce && nonce.match(/^[a-f0-9]+$/)) {
                            return nonce;
                        }
                    }
                    
                    // Try to find in meta tags
                    const metas = document.querySelectorAll('meta[name="nonce"]');
                    for (let meta of metas) {
                        const nonce = meta.getAttribute('content');
                        if (nonce && nonce.match(/^[a-f0-9]+$/)) {
                            return nonce;
                        }
                    }
                    
                    // Try to find in JSON data within scripts
                    for (let script of scripts) {
                        const content = script.textContent || '';
                        try {
                            const jsonMatch = content.match(/\{[^}]*\"nonce\"[^}]*\}/);
                            if (jsonMatch) {
                                const obj = JSON.parse(jsonMatch[0]);
                                if (obj.nonce && typeof obj.nonce === 'string') {
                                    return obj.nonce;
                                }
                            }
                        } catch (e) {
                            // Ignore JSON parse errors
                        }
                    }
                    
                    return null;
                }
            """)
            
            return nonce if nonce else None
        except Exception as e:
            print(f"[Playwright] JavaScript 执行错误: {e}")
            return None

    async def _call_api_with_js(
        self,
        url: str,
        params: Dict[str, Any],
        nonce: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call API endpoint using Playwright's page.evaluate for fetch API.

        Args:
            url: API endpoint URL
            params: Request parameters as dict
            nonce: Security nonce for authentication

        Returns:
            Parsed JSON response as dict, or None if request failed
        """
        try:
            # Use JavaScript fetch API through Playwright
            result = await self.page.evaluate("""
                (url, params, nonce) => {
                    return fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'x-wp-nonce': nonce,
                            'Referer': 'https://getlostinnz.co.nz/',
                            'Origin': 'https://getlostinnz.co.nz'
                        },
                        body: JSON.stringify(params)
                    })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('HTTP error ' + response.status);
                        }
                        return response.json();
                    })
                    .catch(error => {
                        console.error('Fetch error:', error);
                        return null;
                    });
                }
            """, url, params, nonce)
            
            return result if result else None
            
        except Exception as e:
            print(f"[Playwright] JavaScript API 调用错误: {e}")
            return None
