"""
Debug script to check if routes are properly registered
"""
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

# Import the routers
try:
    from src.api.v1.endpoints.scraper_execution_api import router as scraper_router
except ImportError:
    from fastapi import APIRouter
    scraper_router = APIRouter()

from unittest.mock import patch
_patch = patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles')
_patch.start()

try:
    from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
except Exception:
    _patch.stop()
    raise

# Create the test app exactly like in conftest
api_v1_router = APIRouter(prefix='/api/v1')
api_v1_router.include_router(scraper_router, prefix='/scrape', tags=['车辆数据抓取'])
api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])

app = FastAPI()
app.include_router(api_v1_router)
client = TestClient(app)

# Try to access the vehicles endpoint
print("Testing /api/v1/scrape/vehicles:")
response = client.get("/api/v1/scrape/vehicles")
print(f"Status: {response.status_code}")
if response.status_code == 404:
    print("ERROR: Route not found!")
else:
    print(f"Response: {response.text[:200] if response.text else 'No content'}")

# Also test the scraper endpoint
print("\nTesting /api/v1/scrape/execute:")
response = client.post("/api/v1/scrape/execute", json={})
print(f"Status: {response.status_code}")

_patch.stop()
