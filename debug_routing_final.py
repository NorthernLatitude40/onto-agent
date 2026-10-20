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

try:
    from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
except ImportError:
    from fastapi import APIRouter
    vehicle_router = APIRouter()

# Create the v1 router with proper prefix like in the actual app
api_v1_router = APIRouter(prefix='/api/v1')
# scraper_router has endpoints like /scrape/execute
api_v1_router.include_router(scraper_router, prefix='/scrape', tags=['车辆数据抓取'])
# vehicle_router has endpoint at /scrape/vehicles (no additional prefix needed)
api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])

app = FastAPI()
app.include_router(api_v1_router)
client = TestClient(app)

# Print all registered routes
print("\n=== Registered Routes ===")
for route in app.routes:
    print(f"Path: {route.path if hasattr(route, 'path') else 'N/A'}, Methods: {route.methods if hasattr(route, 'methods') else 'N/A'}")

# Try to access the vehicles endpoint
print("\n=== Testing /api/v1/scrape/vehicles ===")
response = client.get("/api/v1/scrape/vehicles")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

# Try to access the execute endpoint
print("\n=== Testing /api/v1/scrape/execute ===")
response = client.get("/api/v1/scrape/execute")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
