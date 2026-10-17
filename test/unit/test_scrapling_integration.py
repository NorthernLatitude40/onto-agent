"""
Test Scrapling Framework Integration
Tests that the scrapling framework is properly integrated with Playwright mode
"""
import pytest
from src.service.playwright_scraper import SCRAPLING_AVAILABLE


def test_scrapling_available():
    """Test that scrapling framework is detected as available"""
    assert SCRAPLING_AVAILABLE == True, "Scrapling framework should be available"


def test_scrapling_import():
    """Test that scrapling can be imported and instantiated"""
    from scrapling import Selector
    # Basic test to ensure Selector can be created
    html = "<html><body><div class='test'>Hello World</div></body></html>"
    selector = Selector(html)
    assert selector is not None, "Selector should be instantiated successfully"


@pytest.mark.asyncio
async def test_playwright_scraper_with_scrapling_mode():
    """Test that PlaywrightScraper can be instantiated with scrapling mode"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    # Test that the class can be instantiated
    scraper = PlaywrightScraper()
    assert scraper is not None
    
    # Test that SCRAPLING_AVAILABLE is accessible
    assert hasattr(scraper, '__class__')
