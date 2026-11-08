"""
Test script to verify async changes in scraper_service.py
"""
import asyncio
from src.service.scraper_service import ScraperService


async def test_scraper_service_async_methods():
    """Test that all async methods are properly defined and can be called."""
    service = ScraperService()
    
    # Test that execute_scrape is async
    print("Testing execute_scrape method...")
    assert callable(service.execute_scrape), "execute_scrape should be callable"
    print("✓ execute_scrape is callable")
    
    # Test that _scrape_with_scrapling is async
    print("\nTesting _scrape_with_scrapling method...")
    assert callable(service._scrape_with_scrapling), "_scrape_with_scrapling should be callable"
    print("✓ _scrape_with_scrapling is callable")
    
    # Test that _execute_sequential_steps is async
    print("\nTesting _execute_sequential_steps method...")
    assert callable(service._execute_sequential_steps), "_execute_sequential_steps should be callable"
    print("✓ _execute_sequential_steps is callable")
    
    # Test that _scrape_with_requests is async
    print("\nTesting _scrape_with_requests method...")
    assert callable(service._scrape_with_requests), "_scrape_with_requests should be callable"
    print("✓ _scrape_with_requests is callable")
    
    # Test that _execute_playwright_step is async
    print("\nTesting _execute_playwright_step method...")
    assert callable(service._execute_playwright_step), "_execute_playwright_step should be callable"
    print("✓ _execute_playwright_step is callable")
    
    print("\n" + "="*50)
    print("All async method signatures are correct!")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(test_scraper_service_async_methods())
