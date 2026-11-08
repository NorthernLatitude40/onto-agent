"""
Simple test for Playwright scrape functionality
"""
import asyncio
from src.service.playwright_scraper import PlaywrightScraper

async def test_simple_scrape():
    """Test the simple scrape method"""
    print("Testing Playwright simple scrape...")
    
    async with PlaywrightScraper() as scraper:
        # Test scraping a simple page
        result = await scraper.scrape(
            url="https://example.com",
            wait_selector=None,
            execute_javascript=None,
            headers={},
            params={},
            browser_options={
                "headless": True,
                "timeout": 30000,
                "viewport": {"width": 1280, "height": 720}
            }
        )
        
        print(f"Result: {result}")
        return result

if __name__ == "__main__":
    result = asyncio.run(test_simple_scrape())
    print(f"Test completed with result length: {len(result) if result else 0}")
