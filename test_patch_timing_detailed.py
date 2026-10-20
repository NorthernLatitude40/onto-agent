"""
Test to verify patch timing
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, APIRouter

print("=== Step 1: Import routers (like in fixture) ===")
try:
    from src.api.v1.endpoints.scraper_execution_api import router as scraper_router
except ImportError:
    from fastapi import APIRouter
    scraper_router = APIRouter()

try:
    from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
except ImportError:
    from fastapi import APIRouter
    vehicle_router = APIRouter()

print(f"Vehicle router imported: {vehicle_router}")
print(f"Vehicle router routes: {[r.path for r in vehicle_router.routes]}")

# Check what vehicle_repo is at this point
from src.api.v1.endpoints.controller.vehicle_routes import vehicle_repo as vr_vehicle_repo
print(f"\nvehicle_repo in vehicle_routes module: {vr_vehicle_repo}")
print(f"Module path: {vr_vehicle_repo.__file__ if hasattr(vr_vehicle_repo, '__file__') else 'N/A'}")

# Now try to patch BEFORE creating the app
print("\n=== Step 2: Apply patch ===")
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
    mock_list.return_value = [{"test": "data"}]
    
    print(f"Mock applied to: src.api.v1.endpoints.dao.vehicle_repo.list_vehicles")
    print(f"Mock function: {mock_list}")
    
    # Create app AFTER patch
    print("\n=== Step 3: Create app and test ===")
    api_v1_router = APIRouter(prefix='/api/v1')
    api_v1_router.include_router(scraper_router, prefix='/scrape', tags=['车辆数据抓取'])
    api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])
    
    app = FastAPI()
    app.include_router(api_v1_router)
    client = TestClient(app)
    
    response = client.get("/api/v1/scrape/vehicles")
    print(f"Status: {response.status_code}")
    print(f"Response data: {response.json()}")
