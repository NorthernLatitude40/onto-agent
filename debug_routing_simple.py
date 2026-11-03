"""
Simple debug script to test if routes are registered correctly
"""
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

# Import the actual routers
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

# List all routes
print("\n=== All registered routes ===")
def print_routes(router, prefix=""):
    for route in router.routes:
        if hasattr(route, 'path'):
            full_path = prefix + route.path
            print(f"Path: {full_path}, Methods: {route.methods}")
        elif hasattr(route, 'app'):
            # This is an included router
            print(f"Included Router at: {prefix}")
            print_routes(route.app, prefix)

print_routes(app, "")

# Try to access the vehicles endpoint
print("\n=== Testing /api/v1/scrape/vehicles ===")
response = client.get("/api/v1/scrape/vehicles")
print(f"Status code: {response.status_code}")
if response.status_code == 404:
    print("ERROR: Route not found!")
elif response.status_code == 200 or response.status_code == 500:
    print("SUCCESS: Route exists and is accessible!")
else:
    print(f"Unexpected status code: {response.status_code}")

print(f"\nResponse: {response.text[:200] if response.text else 'No content'}")
