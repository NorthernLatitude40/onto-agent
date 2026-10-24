#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug script to check all registered routes - simple version"""
from fastapi import FastAPI, APIRouter
from unittest.mock import patch
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
from src.api.v1.endpoints.scraper_config_api import router as scraper_config_router
from src.api.v1.endpoints.controller.scraper_projects import router as scraper_projects_router
from fastapi.testclient import TestClient

# Create test app like in debug_test.py
api_v1_router = APIRouter(prefix='/api/v1')
api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])
api_v1_router.include_router(scraper_config_router, prefix='/vehicles', tags=['爬虫配置管理'])
api_v1_router.include_router(scraper_projects_router, prefix='/vehicles', tags=['车辆配置查询'])

app = FastAPI()
app.include_router(api_v1_router)
client = TestClient(app)

print("=" * 80)
print("Testing different URL patterns:")
print("=" * 80)

# Try the URL from the test
urls_to_test = [
    "/api/v1/vehicles/configs",
    "/api/v1/scrape/vehicles",
    "/api/v1/vehicles/vehicles/configs",
]

for url in urls_to_test:
    print(f"\nTesting: {url}")
    response = client.get(url)
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        print(f"  Response length: {len(response.text)} chars")
    elif response.status_code == 404:
        print(f"  ERROR: Route not found!")
    else:
        print(f"  Error: {response.text[:100]}")

print("\n" + "=" * 80)
