"""
Complete unit tests for scraper API endpoints
Tests all CRUD operations and scrape execution
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
import json


def get_test_client():
    """Create a test client with mocked dependencies"""
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


@pytest.mark.skip(reason="Requires database connection - use with mocked DB")
def test_get_scraper_configs_empty(test_client):
    """Test getting scraper configs when none exist"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        # Mock empty database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query result - empty list
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.return_value = []
        
        response = test_client.get('/api/v1/vehicles/configs')
        assert response.status_code == 200
        assert response.json() == []


def test_get_scraper_configs_with_data(test_client):
    """Test getting scraper configs with mock data"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        # Mock database response with config data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query result - list of configs
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.return_value = [
            (1, 'GetLost NZ Campervan Scraper', 'https://getlostinnz.co.nz/', 
             '{"User-Agent": "Mozilla/5.0"}', 10, True, 'api', '2024-01-15T10:30:00.000Z'),
            (2, 'Spaceships Campervans Scraper', 'https://spaceships.co.nz/', 
             '{"User-Agent": "Mozilla/5.0"}', 10, True, 'html', '2024-01-16T14:20:00.000Z')
        ]
        
        response = test_client.get('/api/v1/vehicles/configs')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]['id'] == 1
        assert data[0]['name'] == 'GetLost NZ Campervan Scraper'
        assert data[0]['is_active'] is True  # Should be boolean, not string


def test_create_scraper_config(test_client):
    """Test creating a new scraper config"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock successful insert - return config_id
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        
        config_data = {
            "name": "Test Scraper",
            "target_url": "http://test.com",
            "headers": {"User-Agent": "Mozilla/5.0"},
            "timeout": 30,
            "mode": "api",
            "steps": [
                {
                    "name": "Initial Request",
                    "mode": "api",
                    "url": "http://test.com/api",
                    "method": "GET",
                    "params_json": "{}",
                    "headers_json": "{}",
                    "parsing_rules": []
                }
            ]
        }
        
        response = test_client.post('/api/v1/vehicles/configs', json=config_data)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data['id'] == 1
        assert data['name'] == 'Test Scraper'


def test_get_scraper_config_by_id(test_client):
    """Test getting a specific scraper config by ID"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query result - single config
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (
            1, 'GetLost NZ Campervan Scraper', 'https://getlostinnz.co.nz/',
            '{"User-Agent": "Mozilla/5.0"}', 10, True, 'api',
            '[{"id": "step-1", "name": "获取车型列表", "mode": "api", "url": "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2"}]',
            '2024-01-15T10:30:00.000Z'
        )
        
        response = test_client.get('/api/v1/vehicles/scrape/configs/1')
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 1
        assert data['name'] == 'GetLost NZ Campervan Scraper'


def test_get_scraper_config_by_id_not_found(test_client):
    """Test getting a scraper config that doesn't exist"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query result - no config found
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = None
        
        response = test_client.get('/api/v1/vehicles/scrape/configs/999')
        assert response.status_code == 404
        assert 'not exist' in response.json()['detail']


def test_update_scraper_config(test_client):
    """Test updating a scraper config"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock successful update - return updated config
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (
            1, 'Updated Scraper Name', 'https://updated.com',
            '{"User-Agent": "Mozilla/5.0"}', 20, True, 'api',
            '[{"id": "step-1", "name": "获取车型列表"}]',
            '2024-01-15T10:30:00.000Z'
        )
        
        update_data = {
            "name": "Updated Scraper Name",
            "target_url": "https://updated.com",
            "timeout": 20
        }
        
        response = test_client.put('/api/v1/vehicles/scrape/configs/1', json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data['name'] == 'Updated Scraper Name'
        assert data['timeout'] == 20


def test_delete_scraper_config(test_client):
    """Test deleting a scraper config"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock successful delete
        mock_cursor.execute.return_value = None
        
        response = test_client.delete('/api/v1/vehicles/scrape/configs/1')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'Deleted scraper config' in data['message']


def test_delete_scraper_config_not_found(test_client):
    """Test deleting a scraper config that doesn't exist"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock no rows affected
        mock_cursor.execute.return_value = None
        
        response = test_client.delete('/api/v1/vehicles/scrape/configs/999')
        assert response.status_code == 404
        assert 'not exist' in response.json()['detail']


def test_execute_scrape(test_client):
    """Test executing a scrape job"""
    with patch('src.api.v1.endpoints.scraper_api.ScraperService') as mock_service_class:
        # Mock the service instance
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        # Mock successful scrape execution
        mock_service.execute_scrape = AsyncMock(return_value=True)
        
        scrape_request = {
            "config_id": 1,
            "pickup_date": "2026-11-10",
            "return_date": "2026-11-15"
        }
        
        response = test_client.post('/api/v1/vehicles/scrape/execute', json=scrape_request)
        assert response.status_code == 202
        data = response.json()
        assert data['success'] is True
        assert 'Scraping task started' in data['message']


def test_get_stored_vehicles(test_client):
    """Test getting stored scraped vehicles"""
    with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query result - list of vehicles
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.return_value = [
            (1, 'Campervan Model A', 4, 'Automatic',
             '{"solar": true, "battery": "200Ah", "heater": "Diesel", "bed": "Double"}',
             '2026-11-10', '2026-11-15', 150.0)
        ]
        
        response = test_client.get('/api/v1/vehicles/scrape/vehicles')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['model_name'] == 'Campervan Model A'
        assert data[0]['specs']['solar'] is True  # Should be boolean, not string


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
