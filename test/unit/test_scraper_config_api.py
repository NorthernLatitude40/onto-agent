"""
Unit tests for scraper configuration API endpoints
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Mock the database and app imports to avoid dependency issues
def get_test_client():
  """Create a test client with mocked dependencies"""
  # Import inside function to ensure proper path resolution
  import sys
  import os
  
  # Add src directory to path
  src_path = os.path.join(os.path.dirname(__file__), "../../src")
  if src_path not in sys.path:
      sys.path.insert(0, src_path)
  
  from fastapi import APIRouter
  from src.api.v1.endpoints.scraper_api import router as scraper_router
  
  # Create the v1 router with proper prefix like in the actual app
  api_v1_router = APIRouter(prefix='/api/v1')
  api_v1_router.include_router(scraper_router, prefix='/vehicles', tags=['车辆数据抓取'])
  
  from fastapi import FastAPI
  app = FastAPI()
  app.include_router(api_v1_router)
  return TestClient(app)

@pytest.fixture(scope="module")
def test_client():
    """Create a test client for the API"""
    yield get_test_client()


def test_get_scraper_configs_empty(test_client):
    """Test getting scraper configs when none exist - mocked version"""
    with patch('api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        # Mock empty database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query result - empty list
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.return_value = []
        
        response = test_client.get("/api/v1/vehicles/configs")
        assert response.status_code == 200
        assert response.json() == []


def test_create_scraper_config(test_client):
    """Test creating a new scraper configuration - mocked version"""
    with patch('api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock the created config object - simulate INSERT returning all fields
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = [
            1,  # id
            "GetLost NZ Campervans",  # name
            "https://getlostinnz.co.nz/",  # target_url
            '{"User-Agent": "Test Agent"}',  # headers (JSON string)
            15,  # timeout
            True,  # is_active
            "api",  # mode
            None,  # created_at
            None   # updated_at
        ]
        
        config_data = {
            "name": "GetLost NZ Campervans",
            "target_url": "https://getlostinnz.co.nz/",
            "headers": {"User-Agent": "Test Agent"},
            "timeout": 15
        }
        
        response = test_client.post("/api/v1/vehicles/configs", json=config_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["name"] == "GetLost NZ Campervans"
        assert data["target_url"] == "https://getlostinnz.co.nz/"
        assert data["timeout"] == 15
        assert data["is_active"] is True
        assert data["mode"] == "api"
        assert "id" in data


def test_get_scraper_configs_with_data(test_client):
    """Test getting scraper configurations when database has data - mocked version"""
    with patch('api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock the SELECT query to return multiple configs
        # Note: The actual query selects id, name, target_url, is_active, mode, created_at
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.return_value = [
            [
                1,  # id
                "GetLost NZ Campervans",  # name
                "https://getlostinnz.co.nz/",  # target_url
                True,  # is_active
                "api",  # mode
                None   # created_at
            ],
            [
                2,  # id
                "Another Scraper",  # name
                "https://another-site.com/",  # target_url
                True,  # is_active
                "html",  # mode
                None   # created_at
            ]
        ]
        
        response = test_client.get("/api/v1/vehicles/configs")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[0]["name"] == "GetLost NZ Campervans"
        assert data[0]["target_url"] == "https://getlostinnz.co.nz/"
        assert data[0]["is_active"] is True
        assert data[0]["mode"] == "api"
        assert data[1]["id"] == 2
        assert data[1]["name"] == "Another Scraper"
        assert data[1]["target_url"] == "https://another-site.com/"
        assert data[1]["is_active"] is True
        assert data[1]["mode"] == "html"
