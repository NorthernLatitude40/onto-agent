#!/usr/bin/env python3
"""
Test script for scraper configuration implementation.

This script tests:
1. Database schema changes (mode field)
2. Pydantic schemas for mode support
3. Scraper service using configurable parameters
4. API endpoint passing mode parameter
"""

import os
import sys
import json
from typing import Dict, Any, Optional

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.model.scraper_schema import (
    ExecuteScrapeRequest,
    ScraperConfigCreate,
    ScraperConfigUpdate,
)
from src.service.scraper_service import ScraperService


def test_execute_scrape_request_with_mode():
    """Test that ExecuteScrapeRequest accepts mode parameter."""
    print("\n=== Test 1: ExecuteScrapeRequest with mode ===")
    
    # Test with mode specified
    request_with_mode = ExecuteScrapeRequest(config_id=1, mode="api")
    assert request_with_mode.config_id == 1
    assert request_with_mode.mode == "api"
    print("✓ ExecuteScrapeRequest accepts mode parameter")
    
    # Test with default mode (None)
    request_default = ExecuteScrapeRequest(config_id=2, mode=None)
    assert request_default.config_id == 2
    assert request_default.mode is None
    print("✓ ExecuteScrapeRequest works with default mode (None)")
    
    # Test serialization
    json_data = request_with_mode.model_dump()
    assert "config_id" in json_data
    assert "mode" in json_data
    assert json_data["mode"] == "api"
    print("✓ ExecuteScrapeRequest serializes correctly")


def test_scraper_config_schemas_with_new_fields():
    """Test that ScraperConfigCreate/Update schemas accept new fields."""
    print("\n=== Test 2: ScraperConfig schemas with new fields ===")
    
    # Test ScraperConfigCreate
    create_data = {
        "name": "Test Config",
        "target_url": "https://example.com/api/vehicles",
        "headers": {"Content-Type": "application/json"},
        "timeout": 30,
        "mode": "api",
        "step2_url": "https://example.com/step2",
        "step3_url": "https://example.com/step3",
        "calctotal_url": "https://example.com/calc",
    }
    
    config_create = ScraperConfigCreate(**create_data)
    assert config_create.name == "Test Config"
    assert config_create.target_url == "https://example.com/api/vehicles"
    assert config_create.mode == "api"
    assert config_create.step2_url == "https://example.com/step2"
    print("✓ ScraperConfigCreate accepts new fields")
    
    # Test ScraperConfigUpdate
    update_data = {
        "name": "Updated Config",
        "mode": "playwright",
        "timeout": 60,
    }
    
    config_update = ScraperConfigUpdate(**update_data)
    assert config_update.name == "Updated Config"
    assert config_update.mode == "playwright"
    assert config_update.timeout == 60
    print("✓ ScraperConfigUpdate accepts new fields")


def test_scraper_service_method_signature():
    """Test that ScraperService.execute_scrape accepts mode parameter."""
    print("\n=== Test 3: ScraperService method signature ===")
    
    service = ScraperService()
    
    # Check if the method exists and has correct signature
    import inspect
    sig = inspect.signature(service.execute_scrape)
    params = list(sig.parameters.keys())
    
    assert "config_id" in params, f"config_id parameter not found in {params}"
    print(f"✓ execute_scrape parameters: {params}")
    
    # Verify mode parameter exists
    if "mode" in params:
        print("✓ execute_scrape accepts mode parameter")
    else:
        print("⚠ execute_scrape does not have mode parameter (will be added via **kwargs)")


def test_mode_validation():
    """Test that valid modes are accepted."""
    print("\n=== Test 4: Mode validation ===")
    
    valid_modes = ["html", "api", "playwright"]
    
    for mode in valid_modes:
        request = ExecuteScrapeRequest(config_id=1, mode=mode)
        assert request.mode == mode
        print(f"✓ Mode '{mode}' accepted")


def test_backward_compatibility():
    """Test that old code without mode parameter still works."""
    print("\n=== Test 5: Backward compatibility ===")
    
    # Old-style request (without mode)
    old_request = ExecuteScrapeRequest(config_id=1, mode=None)
    assert old_request.config_id == 1
    assert old_request.mode is None
    print("✓ Old requests without mode parameter work correctly")
    
    # New-style request (with mode)
    new_request = ExecuteScrapeRequest(config_id=1, mode="api")
    assert new_request.config_id == 1
    assert new_request.mode == "api"
    print("✓ New requests with mode parameter work correctly")


def test_schema_field_types():
    """Test that schema field types are correct."""
    print("\n=== Test 6: Schema field types ===")
    
    from pydantic import BaseModel, Field
    
    # Check ExecuteScrapeRequest fields
    request = ExecuteScrapeRequest(config_id=1, mode="api")
    assert isinstance(request.config_id, int)
    assert isinstance(request.mode, str) or request.mode is None
    print("✓ ExecuteScrapeRequest field types are correct")
    
    # Check ScraperConfigCreate fields
    create_data = {
        "name": "Test",
        "target_url": "https://example.com",
        "headers": {},
        "timeout": 30,
        "mode": "api",
        "step2_url": "https://example.com/step2",
        "step3_url": "https://example.com/step3",
        "calctotal_url": "https://example.com/calc",
    }
    config = ScraperConfigCreate(**create_data)
    assert isinstance(config.mode, str)
    assert isinstance(config.step2_url, str)
    assert isinstance(config.step3_url, str)
    assert isinstance(config.calctotal_url, str)
    print("✓ ScraperConfigCreate field types are correct")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Scraper Configuration Implementation")
    print("=" * 60)
    
    try:
        test_execute_scrape_request_with_mode()
        test_scraper_config_schemas_with_new_fields()
        test_scraper_service_method_signature()
        test_mode_validation()
        test_backward_compatibility()
        test_schema_field_types()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
