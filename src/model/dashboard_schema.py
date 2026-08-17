# src/schema/dashboard_schema.py
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class TrendItem(BaseModel):
    date: str      # 日期展示名称，例如 "08-11" 或 "2026-08"
    income: float  # 阶段总收入
    expense: float # 阶段总支出
    profit: float  # 阶段总毛利

class DashboardOverviewResponse(BaseModel):
    # 动态指标
    profit: float
    income: float
    expense: float
    order_count: int
    in_stock_devices: int

    # 趋势图表数据
    trend: List[TrendItem] = []

    # 原旧字段兼容
    today_profit: Optional[float] = 0.0
    today_income: Optional[float] = 0.0
    today_expense: Optional[float] = 0.0

    class Config:
        orm_mode = True