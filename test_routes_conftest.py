"""
Shared fixtures for route performance tests
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def client():
    """Create a test client with all necessary routers"""
    from fastapi import FastAPI, APIRouter
    
    # Import routers inside fixture to ensure fresh imports for each test
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
    
    try:
        from src.api.v1.endpoints.controller.scraper_projects import router as scraper_projects_router
    except ImportError:
        from fastapi import APIRouter
        scraper_projects_router = APIRouter()
    
    # Create the v1 router with proper prefix like in the actual app
    api_v1_router = APIRouter(prefix='/api/v1')
    # scraper_router has endpoints like /scrape/execute
    api_v1_router.include_router(scraper_router, prefix='/scrape', tags=['车辆数据抓取'])
    # vehicle_router has endpoint at /scrape/vehicles (no additional prefix needed)
    api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])
    # scraper_projects_router has endpoints under /vehicles
    api_v1_router.include_router(scraper_projects_router, prefix='/vehicles', tags=['车辆配置查询'])
    
    app = FastAPI()
    app.include_router(api_v1_router)
    return TestClient(app)
