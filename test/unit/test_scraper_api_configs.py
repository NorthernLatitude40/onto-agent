"""
Unit tests for scraper_api.py - Configuration Management Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from test.unit.conftest_scraper_api import test_client


class TestGetScraperConfigs:
    """Test GET /api/v1/scrape/configs endpoint"""
    
    def test_get_scraper_configs_success(self, test_client):
        """Test successful retrieval of scraper configs"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock empty result
            mock_cursor.fetchall.return_value = []
            
            response = test_client.get("/api/v1/vehicles/configs")
            assert response.status_code == 200
    
    def test_get_scraper_configs_database_error(self, test_client):
        """Test database error handling"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            mock_cursor.execute.side_effect = Exception("DB Error")
    
            response = test_client.get("/api/v1/vehicles/configs")
            assert response.status_code == 500


class TestCreateScraperConfig:
    """Test POST /api/v1/scrape/configs endpoint"""
    
    def test_create_scraper_config_success(self, test_client):
        """Test successful creation of scraper config"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock database query results
            mock_cursor.fetchone.return_value = (
                1,
                "Test Scraper",
                "https://test.com",
                '{"User-Agent": "Test"}',
                15,
                True,
                "api",
                datetime.now(),
                datetime.now()
            )
    
        config_data = {
            "name": "Test Scraper",
            "target_url": "https://test.com",
            "headers": {"User-Agent": "Test"},
            "timeout": 15,
            "mode": "api"
        }
    
        response = test_client.post("/api/v1/vehicles/configs", json=config_data)
        assert response.status_code == 201
        assert response.json()["id"] == 1
        assert response.json()["name"] == "Test Scraper"
    
    def test_create_scraper_config_missing_fields(self, test_client):
        """Test validation for missing required fields"""
        config_data = {
            "name": "Test Scraper"
            # Missing target_url, mode, etc.
        }
    
        response = test_client.post("/api/v1/vehicles/configs", json=config_data)
        assert response.status_code == 422
