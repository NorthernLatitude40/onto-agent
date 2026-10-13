# src/api/v1/endpoints/inventory_api.py
"""
Inventory API main router - aggregates all inventory-related endpoints
"""
from fastapi import APIRouter

# Import sub-routers
from .inventory_device_api import router as device_router
from .inventory_sales_api import router as sales_router
from .inventory_query_api import router as query_router

logger = __name__

router = APIRouter()

# Include all sub-routers
router.include_router(device_router, prefix="/device", tags=["Device Management"])
router.include_router(sales_router, tags=["Sales Management"])
router.include_router(query_router, tags=["Inventory Query"])
