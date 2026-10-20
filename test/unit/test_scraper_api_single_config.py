"""
Unit tests for scraper_api.py - Single Configuration Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from test.unit.conftest_scraper_api import test_client


class TestGetScraperConfig:
    """Test GET /api/v1/scrape/configs/{config_id} endpoint"""
    
    def test_get_scraper_config_success(self, test_client):
        """Test successful retrieval of a specific scraper config"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock database query result
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
    
        response = test_client.get("/api/v1/vehicles/configs/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["name"] == "Test Scraper"
    
    def test_get_scraper_config_not_found(self, test_client):
        """Test handling of non-existent config"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock no result found
            mock_cursor.fetchone.return_value = None
    
        response = test_client.get("/api/v1/vehicles/configs/999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
