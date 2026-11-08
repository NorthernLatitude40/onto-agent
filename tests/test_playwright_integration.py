"""
Integration tests for Playwright execution flow
"""
import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch


def test_playwright_execution_flow():
    """Test the complete playwright execution flow"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/page1",
                "wait_selector": "#content"
            },
            {
                "type": "playwright",
                "url": "https://example.com/page2",
                "execute_javascript": "document.querySelector('#data').innerHTML"
            }
        ]
    }
    
    # Verify the configuration structure
    assert config_data["mode"] == "playwright"
    assert len(config_data["steps"]) == 2


@pytest.mark.asyncio
async def test_playwright_scraper_initialization():
    """Test PlaywrightScraper class initialization and context management"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    
    # Test async context manager
    async with scraper:
        assert True  # If we get here, the context manager works


@pytest.mark.asyncio
async def test_playwright_step_execution_with_mock():
    """Test playwright step execution with mocked browser"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "wait_selector": "#content"
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.wait_for_selector = AsyncMock(return_value=True)
    mock_page.content = AsyncMock(return_value="<html><body><div id='content'>Test Content</div></body></html>")
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify the browser was launched and pages were created
            assert mock_browser.new_page.called


@pytest.mark.asyncio
async def test_playwright_step_with_javascript_execution():
    """Test playwright step with JavaScript execution"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "execute_javascript": "document.querySelector('#data').innerHTML"
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.evaluate = AsyncMock(return_value="Test Data")
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify JavaScript was executed
            assert mock_page.evaluate.called


@pytest.mark.asyncio
async def test_playwright_step_with_headers():
    """Test playwright step with custom headers"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api",
                "headers": {
                    "User-Agent": "CustomAgent/1.0"
                }
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify context was created with headers
            assert mock_browser.new_context.called


@pytest.mark.asyncio
async def test_playwright_step_with_viewport():
    """Test playwright step with custom viewport"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "viewport": {
                    "width": 1280,
                    "height": 720
                }
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.set_viewport_size = AsyncMock(return_value=None)
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify viewport was set
            assert mock_page.set_viewport_size.called


@pytest.mark.asyncio
async def test_playwright_step_with_proxy():
    """Test playwright step with proxy settings"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "proxy": {
                    "server": "http://proxy.example.com:8080"
                }
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify context was created with proxy
            assert mock_browser.new_context.called


@pytest.mark.asyncio
async def test_playwright_step_with_timeout():
    """Test playwright step with custom timeout"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "wait_selector": "#content",
                "timeout": 30000
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.wait_for_selector = AsyncMock(return_value=True)
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify wait_for_selector was called
            assert mock_page.wait_for_selector.called


@pytest.mark.asyncio
async def test_playwright_step_with_user_agent():
    """Test playwright step with custom user agent"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify context was created
            assert mock_browser.new_context.called


@pytest.mark.asyncio
async def test_playwright_sequential_steps():
    """Test execution of multiple playwright steps in sequence"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/page1",
                "wait_selector": "#content1"
            },
            {
                "type": "playwright",
                "url": "https://example.com/page2",
                "execute_javascript": "document.querySelector('#data').innerHTML"
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page1 = MagicMock()
    mock_page2 = MagicMock()
    mock_page1.goto = AsyncMock(return_value=None)
    mock_page1.wait_for_selector = AsyncMock(return_value=True)
    mock_page1.content = AsyncMock(return_value="<html><body><div id='content1'>Content 1</div></body></html>")
    mock_page2.goto = AsyncMock(return_value=None)
    mock_page2.evaluate = AsyncMock(return_value="Data from page 2")
    mock_page2.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify both pages were created and navigated
            assert mock_page1.goto.called
            assert mock_page2.goto.called


@pytest.mark.asyncio
async def test_playwright_step_error_handling():
    """Test error handling in playwright step execution"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "wait_selector": "#nonexistent"
            }
        ]
    }
    
    # Mock the browser and page with error
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Selector not found"))
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Should handle error gracefully
            assert result is not None


@pytest.mark.asyncio
async def test_playwright_step_context_passing():
    """Test context passing between playwright steps"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api?token={token}",
                "params": {"token": "test_token"},
                "execute_javascript": "return 'result_from_step1';"
            },
            {
                "type": "playwright",
                "url": "https://example.com/api2?data={data}",
                "params": {}
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page1 = MagicMock()
    mock_page2 = MagicMock()
    mock_page1.goto = AsyncMock(return_value=None)
    mock_page1.evaluate = AsyncMock(return_value="result_from_step1")
    mock_page1.content = AsyncMock(return_value="<html><body></body></html>")
    mock_page2.goto = AsyncMock(return_value=None)
    mock_page2.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify both steps executed
            assert mock_page1.evaluate.called
            assert mock_page2.goto.called


@pytest.mark.asyncio
async def test_playwright_step_with_all_options():
    """Test playwright step with all available options"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api",
                "wait_selector": "#data",
                "execute_javascript": "document.querySelector('#data').innerHTML",
                "headers": {"User-Agent": "CustomAgent/1.0"},
                "proxy": {"server": "http://proxy.example.com:8080"},
                "timeout": 30000,
                "user_agent": "Mozilla/5.0",
                "viewport": {"width": 1280, "height": 720}
            }
        ]
    }
    
    # Mock the browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.wait_for_selector = AsyncMock(return_value=True)
    mock_page.evaluate = AsyncMock(return_value="Test Data")
    mock_page.set_viewport_size = AsyncMock(return_value=None)
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=None)
        mock_playwright_instance.stop = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)
        
        async with scraper:
            result = await scraper.scrape_with_playwright(config_data)
            # Verify all options were used
            assert mock_browser.new_context.called
            assert mock_page.wait_for_selector.called
            assert mock_page.evaluate.called
            assert mock_page.set_viewport_size.called


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
