from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class DeviceItem(BaseModel):
    imei: str

class PurchaseOrderItem(BaseModel):
    model_name: str
    devices: List[DeviceItem]

class PurchaseDetailResponse(BaseModel):
    id: int
    order_sn: str
    category: int  # 1: 新機, 2: 二手機
    status: int    # 1: 待確認入庫, 2: 已完成入庫
    partner_name: str
    partner_phone: str
    total_amount: float
    created_at: str
    items: List[PurchaseOrderItem]

class ConfirmInboundRequest(BaseModel):
    id: int