"""
Unit tests for scraper_api.py - Stored Vehicles Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock

from test.unit.conftest_scraper_api import test_client


class TestGetStoredVehicles:
    """Test GET /api/v1/scrape/vehicles endpoint"""
    
    def test_get_stored_vehicles_success(self, test_client):
        """Test successful retrieval of stored vehicles"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Mock database query results
            mock_cursor.fetchall.return_value = [
                (1, "Toyota", 3, "Manual", '{"solar": true, "battery": "Lithium 200Ah"}', None, None, 125.0)
            ]
    
        response = test_client.get("/api/v1/vehicles/vehicles")
        assert response.status_code == 200
        assert len(response.json()) >= 1
    
    def test_get_stored_vehicles_database_error(self, test_client):
        """Test database error handling for vehicles endpoint"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            mock_cursor.execute.side_effect = Exception("DB Error")
    
        response = test_client.get("/api/v1/vehicles/vehicles")
        assert response.status_code == 500
