"""Pydantic models local to the scraper API."""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

class ScrapeConfig(BaseModel):
    config_id: Optional[int] = None
    target_url: Optional[str] = None
    headers: Optional[dict] = None
    timeout: Optional[int] = 10


class VehicleSpecs(BaseModel):
    solar: bool = Field(..., example=True)
    battery: str = Field(..., example="Lithium 200Ah")
    heater: str = Field(..., example="Diesel")
    bed: str = Field(..., example="Double")


class ScrapedVehicle(BaseModel):
    model_name: str
    berths: int
    transmission: str
    specs: VehicleSpecs
    price_nzd: Decimal
    pickup_date: Optional[str] = None
    return_date: Optional[str] = None


class ScrapeResponse(BaseModel):
    success: bool
    count: int
    message: str
    vehicles: List[ScrapedVehicle]

# 創建專案的請求驗證模型
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="專案/群組名稱")
    description: Optional[str] = Field(None, max_length=255, description="專案描述")

# 專案回應模型
class ProjectResponse(BaseModel):
    id: int | str  # 視您的資料庫主鍵型態而定 (INT 或 UUID/String)
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True