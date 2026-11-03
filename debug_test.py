"""Debug test to see what's happening"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
from src.api.v1.endpoints.scraper_config_api import router as scraper_config_router
from fastapi import FastAPI, APIRouter

# Create test app like in conftest
api_v1_router = APIRouter(prefix='/api/v1')
api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])
from src.api.v1.endpoints.controller.scraper_projects import router as scraper_projects_router
api_v1_router.include_router(scraper_projects_router, prefix='/vehicles', tags=['车辆配置查询'])
app = FastAPI()
app.include_router(api_v1_router)
client = TestClient(app)

# Test with mock
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
        }
    ]
    
    response = client.get("/api/v1/scrape/vehicles")
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {response.json()}")
    else:
        print(f"Error response: {response.text}")
