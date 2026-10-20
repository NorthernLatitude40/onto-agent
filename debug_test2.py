"""
Debug test to understand the mocking issue
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router

def test_with_debug():
    # Create a simple app with just the vehicle router
    from fastapi import FastAPI, APIRouter
    
    api_v1_router = APIRouter(prefix='/api/v1')
    api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])
    
    app = FastAPI()
    app.include_router(api_v1_router)
    
    client = TestClient(app)
    
    # Apply patch AFTER the module is loaded
    with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_list:
        print(f"Mock object: {mock_list}")
        print(f"Mock return value set to None initially")
        
        # Set the return value
        mock_list.return_value = [
            {"model_name": "Test Vehicle", "berths": 2, "transmission": "Auto"},
            {"model_name": "Test Vehicle 2", "berths": 3, "transmission": "Manual"}
        ]
        print(f"Mock return value: {mock_list.return_value}")
        
        response = client.get("/api/v1/scrape/vehicles")
        print(f"Status code: {response.status_code}")
        print(f"Response JSON: {response.json()}")
        print(f"Response length: {len(response.json())}")

if __name__ == "__main__":
    test_with_debug()
