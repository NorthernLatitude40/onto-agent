"""
Unit tests for vehicle_routes endpoint with proper mocking.

This file demonstrates how to properly mock database calls in FastAPI endpoints
during unit testing, ensuring the mocks are applied before module imports occur.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi.testclient import TestClient


class TestGetStoredVehicles:
    """
    Test suite for GET /api/v1/scrape/vehicles endpoint.
    """

    def test_get_stored_vehicles_success(self, test_client):
        """Test successful retrieval of stored vehicles."""
        response = test_client.get("/api/v1/scrape/vehicles")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[0]["shop"] == "Test Shop 1"
        assert data[0]["model"] == "Model A"
        assert data[1]["id"] == 2
        assert data[1]["shop"] == "Test Shop 2"
        assert data[1]["model"] == "Model B"

    def test_get_stored_vehicles_empty_list(self, test_client):
        """Test retrieval when no vehicles exist."""
        # Override the mock in the fixture for this specific test
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            mock_list.return_value = []
            
            response = test_client.get("/api/v1/scrape/vehicles")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0

    def test_get_stored_vehicles_database_error(self, test_client):
        """Test database error handling."""
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            mock_list.side_effect = Exception("Database connection failed")
            
            response = test_client.get("/api/v1/scrape/vehicles")
            
            assert response.status_code == 500
            assert "数据库查询失败" in response.json()["detail"]

    def test_get_stored_vehicles_response_schema(self, test_client):
        """Test that response matches the expected schema."""
        response = test_client.get("/api/v1/scrape/vehicles")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify each vehicle has required fields
        for vehicle in data:
            assert "id" in vehicle
            assert "shop" in vehicle
            assert "model" in vehicle
            assert "specs" in vehicle
            assert "created_at" in vehicle
            
            # Verify specs structure
            assert isinstance(vehicle["specs"], dict)
            assert "color" in vehicle["specs"]
            assert "price" in vehicle["specs"]

    def test_get_stored_vehicles_with_null_values(self, test_client):
        """Test handling of vehicles with null/None values."""
        with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
            # Create vehicle with None values
            test_vehicle = ScrapedVehicle(
                id=3,
                shop=None,  # Null shop
                model="Model C",
                specs={"color": "green"},  # Missing price
                created_at="2024-01-03"
            )
            mock_list.return_value = [test_vehicle]
            
            response = test_client.get("/api/v1/scrape/vehicles")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            # FastAPI should handle None values appropriately in the response