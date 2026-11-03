"""
Test script to verify patching with test_client fixture
"""
from unittest.mock import patch
from test.unit.conftest_scraper_api import test_client

def test_with_fixture():
    """Test using the actual test_client fixture"""
    # Create a fresh test client
    client = test_client()
    
    with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_list:
        mock_list.return_value = [{"model_name": "Test Vehicle", "berths": 2}]
        
        response = client.get("/api/v1/scrape/vehicles")
        print(f"Status: {response.status_code}")
        print(f"Data: {response.json()}")
        print(f"Mock called: {mock_list.called}")

if __name__ == "__main__":
    test_with_fixture()
