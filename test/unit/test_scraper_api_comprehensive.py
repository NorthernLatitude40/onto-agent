"""
Comprehensive unit tests for scraper API endpoints
Tests all CRUD operations, scrape execution, and edge cases
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


class TestGetScraperConfigs:
    """Test GET /configs endpoint"""
    
    def test_get_scraper_configs_empty(self, test_client):
        """Test getting scraper configs when none exist"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock empty database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock empty result set
            mock_cursor.fetchall.return_value = []
            
            response = test_client.get('/api/v1/vehicles/configs')
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0
    
    def test_get_scraper_configs_with_data(self, test_client):
        """Test getting scraper configs with mock data"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock query result - list of configs
            # Columns must match the SQL query: id, name, target_url, is_active, mode, created_at
            mock_cursor.fetchall.return_value = [
                (1, 'GetLost NZ Scraper', 'https://getlostinnz.co.nz/',
                 True, 'api', '2024-01-15T10:30:00.000Z')
            ]
            
            response = test_client.get('/api/v1/vehicles/configs')
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]['name'] == 'GetLost NZ Scraper'
            assert data[0]['is_active'] is True  # Should be boolean
    
    def test_get_scraper_configs_database_error(self, test_client):
        """Test getting scraper configs when database connection fails"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database connection error
            mock_connect.side_effect = Exception("Connection failed")
            
            response = test_client.get('/api/v1/vehicles/configs')
            assert response.status_code == 500
            assert 'Connection failed' in response.json()['detail']


class TestCreateScraperConfig:
    """Test POST /scrape/configs endpoint"""
    
    def test_create_scraper_config_success(self, test_client):
        """Test creating a new scraper config successfully"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
    
            # Mock successful insert
            mock_cursor.execute.return_value = None
            mock_cursor.fetchone.return_value = (1, 'Test Config', 'https://test.com/',
                                                 '{}', 30, True, 'api', '[]',
                                                 '2024-01-15T10:30:00.000Z', '2024-01-16T14:20:00.000Z')
    
            config_data = {
                "name": "Test Config",
                "target_url": "https://test.com/",
                "headers": {"User-Agent": "Mozilla/5.0"},
                "timeout": 30,
                "is_active": True,
                "mode": "api"
            }
    
            response = test_client.post('/api/v1/vehicles/configs', json=config_data)
            assert response.status_code == 201
            data = response.json()
            assert data['id'] == 1
            assert data['name'] == 'Test Config'
            assert data['is_active'] is True
    
    def test_create_scraper_config_missing_required_fields(self, test_client):
        """Test creating a scraper config with missing required fields"""
        config_data = {
            "name": "Incomplete Config",
            # Missing target_url
        }
        
        response = test_client.post('/api/v1/vehicles/configs', json=config_data)
        assert response.status_code == 422  # Validation error
    
    def test_create_scraper_config_invalid_mode(self, test_client):
        """Test creating a scraper config with invalid mode"""
        config_data = {
            "name": "Invalid Mode Config",
            "target_url": "https://test.com/",
            "mode": "invalid_mode"
        }
        
        response = test_client.post('/api/v1/vehicles/scrape/configs', json=config_data)
        assert response.status_code == 422  # Validation error


class TestGetScraperConfigById:
    """Test GET /scrape/configs/{config_id} endpoint"""
    
    def test_get_scraper_config_by_id_success(self, test_client):
        """Test getting a specific scraper config by ID"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock query result - single config
            mock_cursor.fetchone.return_value = (
                1, 'GetLost NZ Scraper', 'https://getlostinnz.co.nz/',
                '{"User-Agent": "Mozilla/5.0"}', 30, True, 'api', 
                '[{"id": "step-1", "name": "获取车型列表", "mode": "api", "url": "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2"}]',
                '2024-01-15T10:30:00.000Z', '2024-01-16T14:20:00.000Z'
            )
            
            response = test_client.get('/api/v1/vehicles/scrape/configs/1')
            assert response.status_code == 200
            data = response.json()
            assert data['id'] == 1
            assert data['name'] == 'GetLost NZ Scraper'
            assert len(data['steps']) > 0
    
    def test_get_scraper_config_by_id_not_found(self, test_client):
        """Test getting a scraper config that doesn't exist"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response - no result
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_cursor.fetchone.return_value = None
            
            response = test_client.get('/api/v1/vehicles/scrape/configs/999')
            assert response.status_code == 404
            assert 'not exist' in response.json()['detail']
    
    def test_get_scraper_config_by_id_invalid_id(self, test_client):
        """Test getting a scraper config with invalid ID format"""
        # FastAPI will handle this as a path parameter validation
        # This should not reach the endpoint function
        response = test_client.get('/api/v1/vehicles/scrape/configs/invalid')
        assert response.status_code == 422


class TestUpdateScraperConfig:
    """Test PUT /scrape/configs/{config_id} endpoint"""
    
    def test_update_scraper_config_success(self, test_client):
        """Test updating a scraper config successfully"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock successful update
            mock_cursor.execute.return_value = None
            
            config_data = {
                "name": "Updated Config",
                "target_url": "https://updated.com/",
                "timeout": 60,
                "is_active": False
            }
            
            response = test_client.put('/api/v1/vehicles/scrape/configs/1', json=config_data)
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert 'Updated scraper config' in data['message']
    
    def test_update_scraper_config_not_found(self, test_client):
        """Test updating a scraper config that doesn't exist"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response - no rows affected
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_cursor.execute.return_value = None
            
            config_data = {
                "name": "Non-existent Config",
                "target_url": "https://nonexistent.com/"
            }
            
            response = test_client.put('/api/v1/vehicles/scrape/configs/999', json=config_data)
            assert response.status_code == 404
            assert 'not exist' in response.json()['detail']
    
    def test_update_scraper_config_missing_name(self, test_client):
        """Test updating a scraper config with missing name field"""
        # Name is required for update
        config_data = {
            "target_url": "https://test.com/"
            # Missing name
        }
        
        response = test_client.put('/api/v1/vehicles/scrape/configs/1', json=config_data)
        assert response.status_code == 422  # Validation error


class TestDeleteScraperConfig:
    """Test DELETE /scrape/configs/{config_id} endpoint"""
    
    def test_delete_scraper_config_success(self, test_client):
        """Test deleting a scraper config successfully"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
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
    
    def test_delete_scraper_config_not_found(self, test_client):
        """Test deleting a scraper config that doesn't exist"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response - no rows affected
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_cursor.execute.return_value = None
            
            response = test_client.delete('/api/v1/vehicles/scrape/configs/999')
            assert response.status_code == 404
            assert 'not exist' in response.json()['detail']


class TestExecuteScrape:
    """Test POST /scrape/execute endpoint"""
    
    def test_execute_scrape_success(self, test_client):
        """Test executing a scrape job successfully"""
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
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert '已在背景啟動' in data['message']
    
    def test_execute_scrape_with_parsing_rules(self, test_client):
        """Test executing a scrape job with parsing rules"""
        with patch('src.api.v1.endpoints.scraper_api.ScraperService') as mock_service_class:
            # Mock the service instance
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock successful scrape execution
            mock_service.execute_scrape = AsyncMock(return_value=True)
            
            scrape_request = {
                "config_id": 1,
                "pickup_date": "2026-11-10",
                "return_date": "2026-11-15",
                "parsing_rules": [
                    {
                        "id": "rule-1",
                        "name": "解析车型列表",
                        "jsonpath": "$.cars[*].vehiclecategory",
                        "output_field": "model_name",
                        "required": True
                    }
                ]
            }
            
            response = test_client.post('/api/v1/vehicles/scrape/execute', json=scrape_request)
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
    
    def test_execute_scrape_missing_config_id(self, test_client):
        """Test executing a scrape job with missing config_id"""
        scrape_request = {
            # Missing config_id
            "pickup_date": "2026-11-10"
        }
        
        response = test_client.post('/api/v1/vehicles/scrape/execute', json=scrape_request)
        assert response.status_code == 422  # Validation error
    
    def test_execute_scrape_service_error(self, test_client):
        """Test executing a scrape job when service raises an exception"""
        with patch('src.api.v1.endpoints.scraper_api.ScraperService') as mock_service_class:
            # Mock the service instance
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock service error
            mock_service.execute_scrape = AsyncMock(side_effect=Exception("Service error"))
            
            scrape_request = {
                "config_id": 1,
                "pickup_date": "2026-11-10",
                "return_date": "2026-11-15"
            }
            
            response = test_client.post('/api/v1/vehicles/scrape/execute', json=scrape_request)
            assert response.status_code == 500
            assert 'Service error' in response.json()['detail']


class TestGetStoredVehicles:
    """Test GET /scrape/vehicles endpoint"""
    
    def test_get_stored_vehicles_success(self, test_client):
        """Test getting stored scraped vehicles successfully"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock query result - list of vehicles
            mock_cursor.fetchall.return_value = [
                (1, '4WD Campervan', 3, 'Manual', 
                 '{"solar": true, "battery": "100Ah LiFePO4", "heater": "Diesel", "bed": "Double bed"}',
                 125.0, '2026-11-10', '2026-11-15'),
                (2, 'Motorhome', 4, 'Automatic',
                 '{"solar": false, "battery": "80Ah AGM", "heater": "Gas", "bed": "Queen bed"}',
                 150.0, None, None)
            ]
            
            response = test_client.get('/api/v1/vehicles/scrape/vehicles')
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]['model_name'] == '4WD Campervan'
            assert data[0]['specs']['solar'] is True  # Should be boolean, not string
            assert data[1]['specs']['solar'] is False  # Should be boolean, not string
    
    def test_get_stored_vehicles_empty(self, test_client):
        """Test getting stored vehicles when none exist"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database response
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock empty result set
            mock_cursor.fetchall.return_value = []
            
            response = test_client.get('/api/v1/vehicles/scrape/vehicles')
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0
    
    def test_get_stored_vehicles_database_error(self, test_client):
        """Test getting stored vehicles when database connection fails"""
        with patch('src.api.v1.endpoints.scraper_api.psycopg2.connect') as mock_connect:
            # Mock database connection error
            mock_connect.side_effect = Exception("Connection failed")
            
            response = test_client.get('/api/v1/vehicles/scrape/vehicles')
            assert response.status_code == 500
            assert 'Connection failed' in response.json()['detail']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
