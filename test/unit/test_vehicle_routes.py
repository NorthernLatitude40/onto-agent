"""
Unit tests for vehicle_routes.py - Stored Vehicles Endpoints
"""
import pytest
from unittest.mock import patch, MagicMock

from test.unit.conftest_scraper_api import test_client




class TestGetStoredVehicles:
    """Test GET /api/v1/scrape/vehicles endpoint"""
    
    def test_get_stored_vehicles_success(self, test_client):
        """Test successful retrieval of stored vehicles"""
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            mock_list.return_value = [
                {
                    "model_name": "Toyota Hiace",
                    "berths": 3,
                    "transmission": "Manual",
                    "specs": {
                        "solar": True,
                        "battery": "Lithium 200Ah",
                        "heater": "Diesel",
                        "bed": "Double"
                    },
                    "price_nzd": 150.0,
                    "pickup_date": "2024-01-01",
                    "return_date": "2024-01-10"
                },
                {
                    "model_name": "Ford Transit",
                    "berths": 5,
                    "transmission": "Automatic",
                    "specs": {
                        "solar": False,
                        "battery": "Lead Acid",
                        "heater": "Electric",
                        "bed": "Queen"
                    },
                    "price_nzd": 200.0,
                    "pickup_date": None,
                    "return_date": None
                }
            ]
        
        response = test_client.get("/api/v1/scrape/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["model_name"] == "Toyota Hiace"
        assert data[0]["berths"] == 3
        assert data[0]["specs"]["solar"] is True
        assert data[1]["model_name"] == "Ford Transit"
        assert data[1]["specs"]["battery"] == "Lead Acid"
    
    def test_get_stored_vehicles_empty_list(self, test_client):
        """Test retrieval when no vehicles are stored"""
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            mock_list.return_value = []
        
        response = test_client.get("/api/v1/scrape/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
    
    def test_get_stored_vehicles_database_error(self, test_client):
        """Test database error handling for vehicles endpoint"""
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            mock_list.side_effect = Exception("Database connection failed")
        
        response = test_client.get("/api/v1/scrape/vehicles")
        assert response.status_code == 500
        data = response.json()
        assert "数据库查询失败" in data["detail"] or "Database query failed" in data["detail"]
    
    def test_get_stored_vehicles_response_schema(self, test_client):
        """Test that response matches the expected schema"""
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            mock_list.return_value = [
                {
                    "model_name": "Test Vehicle",
                    "berths": 2,
                    "transmission": "Auto",
                    "specs": {
                        "solar": False,
                        "battery": "Unknown",
                        "heater": "Unknown",
                        "bed": "Unknown"
                    },
                    "price_nzd": 0.0,
                    "pickup_date": None,
                    "return_date": None
                }
            ]
        
        response = test_client.get("/api/v1/scrape/vehicles")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        assert "model_name" in data[0]
        assert "berths" in data[0]
        assert "transmission" in data[0]
        assert "specs" in data[0]
        assert "price_nzd" in data[0]
        
        # Verify specs structure
        assert "solar" in data[0]["specs"]
        assert "battery" in data[0]["specs"]
        assert "heater" in data[0]["specs"]
        assert "bed" in data[0]["specs"]
        
        # Verify optional fields
        assert "pickup_date" in data[0]
        assert "return_date" in data[0]

class TestUpdateScraperConfig:
    """Test PUT /scrape/configs/{config_id} endpoint"""

    def test_update_scraper_config_with_group_id(self):
        """Test that PUT /scrape/configs/{config_id} accepts group_id in request body"""
        from fastapi.testclient import TestClient
        from src.api.v1.endpoints.controller.config_routes import router as config_router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(config_router)
        client = TestClient(app)

        # This should pass - group_id is required and correctly formatted
        response = client.put(
            "/scrape/configs/1",
            json={
                "group_id": 1,
                "name": "Updated Config",
                "target_url": "https://example.com",
                "timeout": 30,
                "is_active": True
            }
        )

        # Should not raise validation error about missing group_id
        assert response.status_code != 422

    def test_update_scraper_config_missing_group_id(self):
        """Test that PUT /scrape/configs/{config_id} requires group_id"""
        from fastapi.testclient import TestClient
        from src.api.v1.endpoints.controller.config_routes import router as config_router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(config_router)
        client = TestClient(app)

        # This should fail - group_id is required
        response = client.put(
            "/scrape/configs/1",
            json={
                "name": "Updated Config",
                "target_url": "https://example.com",
                "timeout": 30,
                "is_active": True
                # Missing group_id
            }
        )

        # Should raise validation error about missing required field
        assert response.status_code == 422
