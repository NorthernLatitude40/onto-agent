"""
Unit tests for scraper_api.py - Update and Delete Configuration Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from test.unit.conftest_scraper_api import test_client


class TestUpdateScraperConfig:
    """Test PUT /api/v1/scrape/configs/{config_id} endpoint"""
    
    def test_update_scraper_config_success(self, test_client):
        """Test successful update of scraper config"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock database query results
            mock_cursor.fetchone.side_effect = [
                (1, "Test Scraper", "https://test.com", '{"User-Agent": "Test"}', 15, True, "api", datetime.now(), datetime.now()),  # get config
                None  # check if name exists (none found)
            ]
    
        update_data = {
            "name": "Updated Scraper",
            "target_url": "https://updated.com"
        }
    
        response = test_client.put("/api/v1/vehicles/configs/1", json=update_data)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Scraper"
    
    def test_update_scraper_config_no_fields(self, test_client):
        """Test update with no fields to update"""
        response = test_client.put("/api/v1/vehicles/configs/1", json={})
        assert response.status_code == 400
        assert "no fields" in response.json()["detail"].lower()


class TestDeleteScraperConfig:
    """Test DELETE /api/v1/scrape/configs/{config_id} endpoint"""
    
    def test_delete_scraper_config_success(self, test_client):
        """Test successful deletion of scraper config"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
        response = test_client.delete("/api/v1/vehicles/configs/1")
        assert response.status_code == 204
    
    def test_delete_scraper_config_not_found(self, test_client):
        """Test deletion of non-existent config"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock no result found
            mock_cursor.fetchone.return_value = None
    
        response = test_client.delete("/api/v1/vehicles/configs/999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
