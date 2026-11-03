"""
Unit tests for scraper_api.py - Scrape Execution Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock

from test.unit.conftest_scraper_api import test_client


class TestExecuteScrape:
    """Test POST /api/v1/scrape/execute endpoint"""
    
    def test_execute_scrape_success(self, test_client):
        """Test successful execution of scrape job"""
        with patch('src.api.v1.endpoints.scraper_api.ScraperService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock successful scrape
            mock_service.execute_scrape.return_value = {
                "status": "completed",
                "vehicle_count": 5,
                "config_id": 1
            }
    
        scrape_data = {
            "config_id": 1,
            "scrape_type": "full"
        }
    
        response = test_client.post("/api/v1/vehicles/execute", json=scrape_data)
        assert response.status_code == 200
