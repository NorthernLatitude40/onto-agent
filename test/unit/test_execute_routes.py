"""
Unit tests for execute_routes.py - Scrape Execution Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, APIRouter

from src.api.v1.endpoints.controller.execute_routes import router as execute_router
from src.model.scraper_schema import ExecuteScrapeRequest, ParsingRule


# Mock the database connection before importing the module
@pytest.fixture(autouse=True)
def mock_database_connection():
    """Mock database connection to prevent actual DB calls during tests"""
    with patch('src.service.scraper_service.psycopg2.connect') as mock_connect:
        # Create a mock connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Create a mock cursor
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock fetchone to return a valid config
        mock_cursor.fetchone.return_value = (
            "http://test.com",  # target_url
            '{"User-Agent": "test"}',  # headers
            30,  # timeout
            "api",  # scraper_type
            None,  # base_url
            None,  # api_endpoint
            None,  # calc_total_endpoint
            None,  # default_params
            None,  # sort_order
            None,  # page_size
            None,  # vehicle_type
            None   # steps
        )
        yield


@pytest.fixture(scope="module")
def test_client():
    """Create a test client for the execute API"""
    # Create the v1 router with proper prefix like in the actual app
    api_v1_router = APIRouter(prefix='/api/v1')
    api_v1_router.include_router(execute_router, tags=['爬蟲任務執行'])
    
    app = FastAPI()
    app.include_router(api_v1_router)
    return TestClient(app)


class TestExecuteScrapeEndpoint:
    """Test POST /api/v1/scrape/execute endpoint"""

    def test_execute_scrape_success(self, test_client):
        """Test successful execution of scrape job in background"""
        with patch('src.api.v1.endpoints.controller.execute_routes.ScraperService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock that execute_scrape doesn't raise exceptions
            mock_service.execute_scrape.return_value = None
            
            request_data = {
                "config_id": 1,
                "mode": "api",
                "parsing_rules": [
                    {
                        "name": "解析车型列表",
                        "jsonpath": "$.cars[*].vehiclecategory",
                        "output_field": "model_name",
                        "required": True
                    }
                ]
            }
            
            response = test_client.post("/api/v1/scrape/execute", json=request_data)
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert "ID 为 1 的爬蟲任務已在背景啟動" in result["message"]
    
    def test_execute_scrape_without_parsing_rules(self, test_client):
        """Test execution with no parsing rules (None)"""
        with patch('src.api.v1.endpoints.controller.execute_routes.ScraperService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            request_data = {
                "config_id": 2,
                "mode": "browser"
            }
            
            response = test_client.post("/api/v1/scrape/execute", json=request_data)
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
    
    def test_execute_scrape_empty_parsing_rules(self, test_client):
        """Test execution with empty parsing rules list"""
        with patch('src.api.v1.endpoints.controller.execute_routes.ScraperService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            request_data = {
                "config_id": 3,
                "mode": "api",
                "parsing_rules": []
            }
            
            response = test_client.post("/api/v1/scrape/execute", json=request_data)
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
    
    def test_execute_scrape_service_exception(self, test_client):
        """Test that service exceptions are properly handled"""
        with patch('src.api.v1.endpoints.controller.execute_routes.ScraperService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock execute_scrape to raise an exception
            mock_service.execute_scrape.side_effect = Exception("Database connection failed")
            
            request_data = {
                "config_id": 4,
                "mode": "api"
            }
            
            response = test_client.post("/api/v1/scrape/execute", json=request_data)
            # The exception is caught and converted to HTTPException with status 500
            # But the background task still returns success since it was added successfully
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
    
    def test_execute_scrape_missing_config_id(self, test_client):
        """Test that missing config_id results in validation error"""
        request_data = {
            "mode": "api"
        }
        
        response = test_client.post("/api/v1/scrape/execute", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_rules_to_dicts_function(self, test_client):
        """Test the _rules_to_dicts helper function"""
        from src.api.v1.endpoints.controller.execute_routes import _rules_to_dicts
        
        # Test with None
        result = _rules_to_dicts(None)
        assert result is None
        
        # Test with empty list
        result = _rules_to_dicts([])
        assert result is None
        
        # Test with actual rules
        rule1 = ParsingRule(
            name="rule1",
            jsonpath="$.field1",
            output_field="output1",
            required=True
        )
        rule2 = ParsingRule(
            name="rule2",
            css_selector="div.content",
            output_field="output2",
            required=False
        )
        
        result = _rules_to_dicts([rule1, rule2])
        assert len(result) == 2
        assert result[0]["name"] == "rule1"
        assert result[0]["jsonpath"] == "$.field1"
        assert result[0]["output_field"] == "output1"
        assert result[0]["required"] is True
        assert result[1]["name"] == "rule2"
        assert result[1]["css_selector"] == "div.content"
        assert result[1]["output_field"] == "output2"
        assert result[1]["required"] is False
