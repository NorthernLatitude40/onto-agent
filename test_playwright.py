#!/usr/bin/env python3
"""
Test script to verify Playwright installation and basic functionality.
"""
import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    """Test if Playwright can launch a browser and navigate to a page."""
    print("Testing Playwright installation...")
    
    try:
        async with async_playwright() as p:
            # Launch Chromium
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Navigate to a simple page
            await page.goto("https://example.com")
            title = await page.title()
            
            print(f"✓ Playwright is working! Page title: {title}")
            
            await browser.close()
            return True
    except Exception as e:
        print(f"✗ Playwright test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_playwright())
    exit(0 if result else 1)
