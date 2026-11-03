#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug script to check all registered routes"""
from fastapi import FastAPI, APIRouter
from unittest.mock import patch
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router
from src.api.v1.endpoints.scraper_config_api import router as scraper_config_router
from src.api.v1.endpoints.controller.scraper_projects import router as scraper_projects_router

def print_routes(app, prefix=""):
    """Recursively print all routes with their full paths"""
    for route in app.routes:
        if hasattr(route, 'app'):  # This is an included router
            # Get the actual FastAPI app from the included router
            included_app = route.app
            new_prefix = prefix + route.path if route.path else prefix
            print_routes(included_app, new_prefix)
        elif hasattr(route, 'endpoint'):
            full_path = prefix + route.path if route.path else prefix
            method_names = ", ".join([m.method.upper() for m in route.methods])
            print(f"{method_names:10} {full_path}")

# Create test app like in debug_test.py
api_v1_router = APIRouter(prefix='/api/v1')
api_v1_router.include_router(vehicle_router, tags=['车辆数据查询'])
api_v1_router.include_router(scraper_config_router, prefix='/vehicles', tags=['爬虫配置管理'])
api_v1_router.include_router(scraper_projects_router, prefix='/vehicles', tags=['车辆配置查询'])

app = FastAPI()
app.include_router(api_v1_router)

print("=" * 80)
print("All registered routes:")
print("=" * 80)
print_routes(app)
print("=" * 80)
