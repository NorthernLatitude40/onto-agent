# src/schema/dashboard_schema.py
from pydantic import BaseModel, ConfigDict, Field


class DashboardOverviewResponse(BaseModel):
    """首页概览数据响应模型 (Bare Payload)"""
    today_profit: float = Field(default=0.0, description="今日总毛利")
    today_income: float = Field(default=0.0, description="今日总收入")
    today_expense: float = Field(default=0.0, description="今日总支出")
    in_stock_devices: int = Field(default=0, description="在库设备总台数")

    model_config = ConfigDict(from_attributes=True)