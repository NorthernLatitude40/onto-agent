"""
Dashboard API Endpoints

This module provides dashboard-related endpoints including:
- Overview statistics (/dashboard/overview)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from src.model.response_models import ApiResponse, DashboardOverviewData
from src.common.exceptions import UnauthorizedError

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewData,
    summary="獲取儀表板概覽數據",
    description="返回當前門店的銷售、庫存和財務概覽"
)
async def get_dashboard_overview():
    """
    獲取儀表板概覽數據
    
    Returns:
        DashboardOverviewData: 包含銷售、庫存和財務統計的概覽數據
    
    Raises:
        UnauthorizedError: 如果用戶未登錄或會話無效
    """
    # TODO: Implement actual dashboard logic with real data
    return DashboardOverviewData(
        sales_stats={
            "total_sales": 150,
            "today_sales": 25,
            "pending_refunds": 3
        },
        inventory_stats={
            "total_devices": 450,
            "in_stock": 380,
            "out_of_stock": 70
        },
        financial_stats={
            "total_revenue": 12500.00,
            "today_revenue": 2250.50,
            "pending_payments": 1800.00
        }
    )
