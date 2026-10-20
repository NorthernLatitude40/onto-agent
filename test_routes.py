"""Debug script to check registered routes"""
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from src.api.v1.endpoints.scraper_execution_api import router as scraper_router
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router

# Create test app like in conftest
api_v1_router = APIRouter(prefix='/api/v1')
api_v1_router.include_router(scraper_router, prefix='/vehicles', tags=['车辆数据抓取'])
api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])

app = FastAPI()
app.include_router(api_v1_router)
client = TestClient(app)

print("Testing endpoints:")
print("GET /api/v1/scrape/vehicles:", end=" ")
response = client.get("/api/v1/scrape/vehicles")
print(f"Status: {response.status_code}")

print("POST /api/v1/vehicles/scrape/execute:", end=" ")
response = client.post("/api/v1/vehicles/scrape/execute", json={"config_id": 1})
print(f"Status: {response.status_code}")
