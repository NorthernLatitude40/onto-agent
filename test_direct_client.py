"""
Test script with direct test client setup
"""
from unittest.mock import patch
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

def create_test_client():
    """Create a test client for the scraper API"""
    from fastapi import FastAPI, APIRouter
    # Import routers inside fixture to ensure fresh imports for each test
    try:
        from src.api.v1.endpoints.scraper_execution_api import router as scraper_router
    except ImportError:
        scraper_router = APIRouter()

    try:
        from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
    except ImportError:
        vehicle_router = APIRouter()

    # Create the v1 router with proper prefix like in the actual app
    api_v1_router = APIRouter(prefix='/api/v1')
    # scraper_router has endpoints like /scrape/execute
    api_v1_router.include_router(scraper_router, prefix='/scrape', tags=['车辆数据抓取'])
    # vehicle_router has endpoint at /scrape/vehicles (no additional prefix needed)
    api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])

    app = FastAPI()
    app.include_router(api_v1_router)
    return TestClient(app)

def test_with_mock():
    """Test using the actual test_client fixture"""
    client = create_test_client()
    
    with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_list:
        # Mock data matching the ScrapedVehicle schema
        mock_list.return_value = [{
            "model_name": "Test Vehicle",
            "berths": 2,
            "transmission": "Automatic",
            "specs": {"engine": "V6"},
            "price_nzd": 50000
        }]
        
        response = client.get("/api/v1/scrape/vehicles")
        print(f"Status: {response.status_code}")
        print(f"Data: {response.json()}")
        print(f"Mock called: {mock_list.called}")

if __name__ == "__main__":
    test_with_mock()
