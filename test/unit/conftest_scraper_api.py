"""
Shared fixtures for scraper API tests
"""
import pytest
from fastapi.testclient import TestClient

# Import routers inside the fixture to ensure fresh imports for each test


@pytest.fixture(scope="function")
def test_client():
   """Create a test client for the scraper API"""
   from fastapi import FastAPI, APIRouter
   
   # Import routers inside fixture to ensure fresh imports for each test
   try:
       from src.api.v1.endpoints.scraper_execution_api import router as scraper_router
   except ImportError:
       # If scraper_execution_api doesn't exist, create a dummy router
       from fastapi import APIRouter
       scraper_router = APIRouter()
   
   try:
       from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
   except ImportError:
       # If vehicle_routes doesn't exist, create a dummy router
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
   return TestClient(app)
