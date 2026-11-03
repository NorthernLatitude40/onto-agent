from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# --- Van Model Schemas ---
class VanModelBase(BaseModel):
  model_name: str = Field(..., max_length=100)
  berths: Optional[int] = 2
  transmission: Optional[str] = None
  specs: Optional[Dict[str, Any]] = None


class VanModelResponse(VanModelBase):
  id: int
  created_at: Optional[datetime] = None

  class Config:
    from_attributes = True


# --- Pricing Inventory Schemas ---
class PricingInventoryBase(BaseModel):
  model_id: Optional[int] = None
  price_nzd: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2)
  is_available: Optional[bool] = True
  pickup_location: Optional[str] = Field(None, max_length=100)
  return_location: Optional[str] = Field(None, max_length=100)
  start_time: Optional[datetime] = None
  end_time: Optional[datetime] = None


class PricingInventoryCreate(PricingInventoryBase):
  pass


class PricingInventoryUpdate(PricingInventoryBase):
  pass


class PricingInventoryResponse(PricingInventoryBase):
  id: int
  updated_at: Optional[datetime] = None

  class Config:
    from_attributes = True


# 联表带车辆详情的响应
class PricingInventoryWithVanResponse(PricingInventoryResponse):
  van_model: Optional[VanModelResponse] = None