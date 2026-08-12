from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from src.common.database import get_db
from src.api.auth_api import get_current_user    # 获取当前登录用户/店铺权限

class StockItemOut(BaseModel):
    id: int
    title: Optional[str] = None
    model: Optional[str] = None
    spec: Optional[str] = None
    purchase_price: Optional[float] = 0.0
    cost: Optional[float] = 0.0
    status: int
    sn: Optional[str] = None  # 设备序列号/IMEI（如有）

    model_config = ConfigDict(from_attributes=True)

class StockListResponse(BaseModel):
    items: List[StockItemOut]