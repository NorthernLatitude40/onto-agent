#!/usr/bin/env python3
"""
Unit tests for config_routes.py API endpoints.

Tests all CRUD operations by mocking the database layer:
1. GET /configs - List active configs
2. POST /configs - Create new config
3. GET /scrape/configs/{config_id} - Get specific config
4. PUT /scrape/configs/{config_id} - Update config
5. DELETE /scrape/configs/{config_id} - Soft delete config
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.v1.endpoints.controller.config_routes import (
    get_scraper_configs,
    create_scraper_config,
    get_scraper_config,
    update_scraper_config,
    delete_scraper_config,
)
from fastapi import HTTPException
from src.model.scraper_schema import (
    ScraperConfigCreate,
    ScraperConfigUpdate,
)


def test_get_scraper_configs_success():
    """Test GET /configs returns list of active configs."""
    print("\n=== Test 1: get_scraper_configs - Success ===")
    
    # Mock successful database response
    mock_configs = [
        {
            "id": 1,
            "name": "Test Config 1",
            "target_url": "https://example.com/1",
            "is_active": True,
            "mode": "api",
            "created_at": "2024-01-15T10:30:00.000Z"
        },
        {
            "id": 2,
            "name": "Test Config 2",
            "target_url": "https://example.com/2",
            "is_active": True,
            "mode": "html",
            "created_at": "2024-01-16T10:30:00.000Z"
        }
    ]
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.list_active', return_value=mock_configs):
        result = get_scraper_configs()
        
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Test Config 1"
        assert result[0]["mode"] == "api"
        print("✓ get_scraper_configs returns correct list of active configs")


def test_get_scraper_configs_database_error():
    """Test GET /configs handles database errors."""
    print("\n=== Test 2: get_scraper_configs - Database Error ===")
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.list_active', side_effect=Exception("DB error")):
        try:
            get_scraper_configs()
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 500
            assert "数据库操作失败" in str(e.detail)
            print("✓ get_scraper_configs raises HTTPException on database error")


def test_create_scraper_config_success():
    """Test POST /configs creates new config successfully."""
    print("\n=== Test 3: create_scraper_config - Success ===")
    
    # Create a proper Pydantic model instance
    config_data = ScraperConfigCreate(
        name="New Scraper Config",
        target_url="https://example.com/api",
        headers={"User-Agent": "Test"},
        timeout=30,
        mode="api"
    )
    
    mock_response = {
        "id": 1,
        "name": "New Scraper Config",
        "target_url": "https://example.com/api",
        "headers": {"User-Agent": "Test"},
        "timeout": 30,
        "is_active": True,
        "mode": "api",
        "created_at": "2024-01-15T10:30:00.000Z",
        "updated_at": None
    }
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.create', return_value=mock_response):
        result = create_scraper_config(config_data)
        
        assert result["id"] == 1
        assert result["name"] == "New Scraper Config"
        assert result["timeout"] == 30
        print("✓ create_scraper_config creates config with correct data")


def test_create_scraper_config_database_error():
    """Test POST /configs handles database errors."""
    print("\n=== Test 4: create_scraper_config - Database Error ===")
    
    config_data = ScraperConfigCreate(
        name="New Config",
        target_url="https://example.com",
        headers={},
        timeout=10,
        mode="html"
    )
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.create', side_effect=Exception("DB error")):
        try:
            create_scraper_config(config_data)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 500
            assert "数据库操作失败" in str(e.detail)
            print("✓ create_scraper_config raises HTTPException on database error")


def test_get_scraper_config_by_id_success():
    """Test GET /scrape/configs/{config_id} returns config."""
    print("\n=== Test 5: get_scraper_config - Success ===")
    
    mock_config = {
        "id": 1,
        "name": "Test Config",
        "target_url": "https://example.com",
        "headers": {"User-Agent": "Test"},
        "timeout": 30,
        "is_active": True,
        "mode": "api",
        "created_at": "2024-01-15T10:30:00.000Z",
        "updated_at": None
    }
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.get_by_id', return_value=mock_config):
        result = get_scraper_config(1)
        
        assert result["id"] == 1
        assert result["name"] == "Test Config"
        assert result["timeout"] == 30
        print("✓ get_scraper_config returns correct config details")


def test_get_scraper_config_by_id_not_found():
    """Test GET /scrape/configs/{config_id} handles not found."""
    print("\n=== Test 6: get_scraper_config - Not Found ===")
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.get_by_id', return_value=None):
        try:
            get_scraper_config(999)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert "爬虫配置 ID 999 不存在" in str(e.detail)
            print("✓ get_scraper_config raises HTTPException when config not found")


def test_get_scraper_config_by_id_database_error():
    """Test GET /scrape/configs/{config_id} handles database errors."""
    print("\n=== Test 7: get_scraper_config - Database Error ===")
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.get_by_id', side_effect=Exception("DB error")):
        try:
            get_scraper_config(1)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 500
            assert "数据库操作失败" in str(e.detail)
            print("✓ get_scraper_config raises HTTPException on database error")


def test_update_scraper_config_success():
    """Test PUT /scrape/configs/{config_id} updates config."""
    print("\n=== Test 8: update_scraper_config - Success ===")
    
    config_data = ScraperConfigUpdate(
        name="Updated Config",
        target_url=None,
        headers=None,
        timeout=60,
        is_active=True
    )
    
    mock_response = {
        "id": 1,
        "name": "Updated Config",
        "target_url": "https://example.com",
        "headers": {"User-Agent": "Test"},
        "timeout": 60,
        "is_active": True,
        "mode": "api",
        "created_at": "2024-01-15T10:30:00.000Z",
        "updated_at": "2024-01-16T10:30:00.000Z"
    }
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.update', return_value=mock_response):
        result = update_scraper_config(1, MockUpdateRequest())
        
        assert result["id"] == 1
        assert result["name"] == "Updated Config"
        assert result["timeout"] == 60
        print("✓ update_scraper_config updates config correctly")


def test_update_scraper_config_not_found():
    """Test PUT /scrape/configs/{config_id} handles not found."""
    print("\n=== Test 9: update_scraper_config - Not Found ===")
    
    config_data = ScraperConfigUpdate(
        name="Updated Config",
        target_url=None,
        headers=None,
        timeout=60,
        is_active=None
    )
    
    with patch('src.api.v1.endpoints.controller.config_routes.config_repo.update', return_value=None):
        try:
            update_scraper_config(999, config_data)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert "爬虫配置 ID 999 不存在" in str(e.detail)
            print("✓ update_scraper_config raises HTTPException when config not found")


def test_update_scraper_config_database_error():
    """Test PUT /scrape/configs/{config_id} handles database errors."""
    print("\n=== Test 10: update_scraper_config - Database Error ===")
