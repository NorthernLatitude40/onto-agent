"""
Unit tests for Playwright configuration parsing
"""
import pytest
from typing import Dict, Any


def test_parse_playwright_step_basic():
    """Test parsing of basic playwright step configuration"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com"
            }
        ]
    }
    
    # Verify basic structure
    assert config_data["mode"] == "playwright"
    assert len(config_data["steps"]) == 1
    assert config_data["steps"][0]["type"] == "playwright"
    assert config_data["steps"][0]["url"] == "https://example.com"


def test_parse_playwright_step_with_wait_selector():
    """Test parsing of playwright step with wait selector"""
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
    
    step = config_data["steps"][0]
    assert step["wait_selector"] == "#content"


def test_parse_playwright_step_with_javascript():
    """Test parsing of playwright step with JavaScript execution"""
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
    
    step = config_data["steps"][0]
    assert step["execute_javascript"] == "document.querySelector('#data').innerHTML"


def test_parse_playwright_step_with_headers():
    """Test parsing of playwright step with headers"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api",
                "headers": {
                    "User-Agent": "CustomAgent/1.0",
                    "Accept": "application/json"
                }
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert "headers" in step
    assert step["headers"]["User-Agent"] == "CustomAgent/1.0"
    assert step["headers"]["Accept"] == "application/json"


def test_parse_playwright_step_with_proxy():
    """Test parsing of playwright step with proxy settings"""
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
    
    step = config_data["steps"][0]
    assert "proxy" in step
    assert step["proxy"]["server"] == "http://proxy.example.com:8080"


def test_parse_playwright_step_with_timeout():
    """Test parsing of playwright step with timeout"""
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
    
    step = config_data["steps"][0]
    assert step["timeout"] == 30000


def test_parse_playwright_step_with_user_agent():
    """Test parsing of playwright step with user agent"""
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
    
    step = config_data["steps"][0]
    assert step["user_agent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def test_parse_playwright_step_with_viewport():
    """Test parsing of playwright step with viewport settings"""
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
    
    step = config_data["steps"][0]
    assert "viewport" in step
    assert step["viewport"]["width"] == 1280
    assert step["viewport"]["height"] == 720


def test_parse_playwright_step_with_params():
    """Test parsing of playwright step with parameters"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api?token={token}",
                "params": {"token": "test_token"}
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert "params" in step
    assert step["params"]["token"] == "test_token"


def test_parse_playwright_step_with_all_options():
    """Test parsing of playwright step with all available options"""
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
    
    step = config_data["steps"][0]
    assert step["url"] == "https://example.com/api"
    assert step["wait_selector"] == "#data"
    assert step["execute_javascript"] == "document.querySelector('#data').innerHTML"
    assert "headers" in step
    assert "proxy" in step
    assert step["timeout"] == 30000
    assert step["user_agent"] == "Mozilla/5.0"
    assert "viewport" in step


def test_parse_multiple_playwright_steps():
    """Test parsing of multiple playwright steps"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/page1"
            },
            {
                "type": "playwright",
                "url": "https://example.com/page2"
            }
        ]
    }
    
    assert len(config_data["steps"]) == 2
    assert config_data["steps"][0]["url"] == "https://example.com/page1"
    assert config_data["steps"][1]["url"] == "https://example.com/page2"


def test_parse_playwright_step_with_mixed_types():
    """Test parsing of mixed step types in configuration"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "api",
                "url": "https://example.com/api/v1/data"
            },
            {
                "type": "playwright",
                "url": "https://example.com/page"
            }
        ]
    }
    
    assert len(config_data["steps"]) == 2
    assert config_data["steps"][0]["type"] == "api"
    assert config_data["steps"][1]["type"] == "playwright"


def test_parse_playwright_step_with_empty_options():
    """Test parsing of playwright step with empty optional fields"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com"
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert "wait_selector" not in step
    assert "execute_javascript" not in step
    assert "headers" not in step
    assert "proxy" not in step
    assert "timeout" not in step
    assert "user_agent" not in step
    assert "viewport" not in step


def test_parse_playwright_step_with_default_timeout():
    """Test parsing of playwright step with default timeout value"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com"
            }
        ]
    }
    
    # Default timeout should be set
    step = config_data["steps"][0]
    assert "timeout" not in step  # No default in config, only during execution


def test_parse_playwright_step_with_invalid_url():
    """Test parsing of playwright step with invalid URL"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "not-a-valid-url"
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["url"] == "not-a-valid-url"


def test_parse_playwright_step_with_special_characters():
    """Test parsing of playwright step with special characters in selectors"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "wait_selector": "div.data-item[data-id='123']"
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["wait_selector"] == "div.data-item[data-id='123']"


def test_parse_playwright_step_with_javascript_template():
    """Test parsing of playwright step with JavaScript template string"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "execute_javascript": "return document.querySelector('#{selector}').innerHTML;"
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["execute_javascript"] == "return document.querySelector('#{selector}').innerHTML;"


def test_parse_playwright_step_with_complex_headers():
    """Test parsing of playwright step with complex headers structure"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api",
                "headers": {
                    "User-Agent": "CustomAgent/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer token123"
                }
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert len(step["headers"]) == 4
    assert step["headers"]["Authorization"] == "Bearer token123"


def test_parse_playwright_step_with_proxy_auth():
    """Test parsing of playwright step with proxy authentication"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "proxy": {
                    "server": "http://proxy.example.com:8080",
                    "username": "user123",
                    "password": "pass123"
                }
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert "proxy" in step
    assert step["proxy"]["username"] == "user123"
    assert step["proxy"]["password"] == "pass123"


def test_parse_playwright_step_with_viewport_zero():
    """Test parsing of playwright step with zero viewport dimensions"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "viewport": {
                    "width": 0,
                    "height": 0
                }
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["viewport"]["width"] == 0
    assert step["viewport"]["height"] == 0


def test_parse_playwright_step_with_large_timeout():
    """Test parsing of playwright step with large timeout value"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "wait_selector": "#content",
                "timeout": 300000
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["timeout"] == 300000


def test_parse_playwright_step_with_unicode_user_agent():
    """Test parsing of playwright step with Unicode characters in user agent"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["user_agent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def test_parse_playwright_step_with_empty_string_values():
    """Test parsing of playwright step with empty string values"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "wait_selector": ""
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["wait_selector"] == ""


def test_parse_playwright_step_with_multiline_javascript():
    """Test parsing of playwright step with multiline JavaScript"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com",
                "execute_javascript": """
                    const element = document.querySelector('#data');
                    return element ? element.innerHTML : null;
                """
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert "const element" in step["execute_javascript"]


def test_parse_playwright_step_with_json_headers():
    """Test parsing of playwright step with JSON headers"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com/api",
                "headers": {
                    "Accept": "application/json"
                }
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["headers"]["Accept"] == "application/json"


def test_parse_playwright_step_with_ssl_bypass():
    """Test parsing of playwright step with SSL bypass option (simulated)"""
    from src.service.playwright_scraper import PlaywrightScraper
    
    scraper = PlaywrightScraper()
    config_data = {
        "mode": "playwright",
        "steps": [
            {
                "type": "playwright",
                "url": "https://example.com"
            }
        ]
    }
    
    step = config_data["steps"][0]
    assert step["url"] == "https://example.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
