from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer
from decimal import Decimal
from enum import Enum, IntEnum
from datetime import datetime, timezone

from src.common.database import get_db
from src.api.auth_api import get_current_user    # 获取当前登录用户/店铺权限
from src.common.dict import DeviceTypeEnum
from src.common.dict import StockStatusEnum

class StockItemOut(BaseModel):
    id: int
    title: Optional[str] = None
    model: Optional[str] = None
    category: Optional[int] = None
    spec: Optional[str] = None
    purchase_price: Optional[float] = 0.0
    cost: Optional[float] = 0.0
    status: int
    sn_code: Optional[str] = None  # 設備序列號/IMEI（如有）

    # 🌟 隱藏欄位：從 ORM 讀取入庫時間（不會出現在 JSON 響應中）
    in_stock_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


    # 🌟 核心：自動將 datetime 欄位序列化為帶 UTC 標記的 ISO 8601 字串
    @field_serializer("in_stock_time", "created_at", check_fields=False)
    def serialize_dt_to_iso(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        # 如果是 Naive datetime (無時區資訊)，強制補上 UTC 時區標籤
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    # 🌟 計算屬性：自動計算庫齡（天數）並加入返回 JSON 中
    @computed_field
    @property
    def stock_age(self) -> int:
        """
        根據 in_stock_time 計算庫齡（天數）。
        若無入庫時間，預設返回 0 天。
        """
        if not self.in_stock_time:
            return 0

        # 處理時區相容性（帶時區與不帶時區的轉換）
        now = datetime.now(timezone.utc)
        
        # 若資料庫的 datetime 沒有時區資訊，則統一取無時區的 UTC 時間計算
        if self.in_stock_time.tzinfo is None:
            now = datetime.utcnow()

        delta = now - self.in_stock_time
        return max(0, delta.days)  # 確保不為負數

class StockListResponse(BaseModel):
    items: List[StockItemOut]

class SellDeviceResponse(BaseModel):
    id: int = Field(..., description="设备 ID")
    model: str = Field(..., description="设备型号/名称")
    order_sn: str = Field(..., description="生成的出库订单号")
    sell_price: float = Field(..., description="实际出售价格")
    profit: float = Field(..., description="本次交易利润")

from pydantic import BaseModel, Field
from typing import List, Optional

# 1. 單個設備明細模型
class PurchaseOrderItemPayload(BaseModel):
    type: DeviceTypeEnum = Field(..., description="分類類型: 1=新機, 2=二手機, 3=配件")
    model_name: str = Field(..., description="設備機型名稱，如：iPhone 15 Pro")
    serials: List[str] = Field(default_factory=list, description="串號/IMEI/SN列表")
    cost_price: float = Field(0.0, description="進貨/回收單價")
    notes: str = Field(None, description="備注")


# 2. 待入庫單據主 Payload 模型 (對應前端 payload)
class CreatePurchaseOrderPayload(BaseModel):
    supplier_phone: str = Field(..., description="聯繫電話")
    supplier_name: Optional[str] = Field(default="", description="姓名/單位名稱")
    partner_id: Optional[int] = Field(default=None, description="往來單位ID（客戶/供應商ID）")
    operator_id: Optional[int] = Field(default=None, description="經手人/當前登入員工ID")
    total_amount: float = Field(0.0, description="採購總額")
    status: str = Field(default="pending", description="單據狀態：pending-待入庫 / completed-已入庫")
    items: List[PurchaseOrderItemPayload] = Field(..., description="設備明細列表")

class AddDeviceConfirmPayload(BaseModel):
    model: str = Field(..., description="设备型号，如：iPhone 13 128G")
    cost: float = Field(..., description="采购/回收成本价")
    partner_id: Optional[int] = Field(default=None, description="往来单位ID（客户/供应商ID）")
    color: Optional[str] = Field(default="未知", description="设备颜色")
    notes: Optional[str] = Field(default="二手回收", description="备注信息")

class SalesItemPayload(BaseModel):
    inventory_id: int = Field(..., description="庫存設備 ID")
    sale_price: Decimal = Field(..., gt=0, description="實際銷售價格")


class CreateOutboundOrderPayload(BaseModel):
    customer_id: Optional[int] = Field(None, description="客戶 ID (partner 表)")
    outbound_type: int = Field(1, description="出貨類型: 1-零售銷售, 2-批發出貨")
    items: List[SalesItemPayload] = Field(..., min_items=1, description="銷售商品列表")
    remark: Optional[str] = Field(None, description="備註資訊")
    auto_deliver: Optional[bool] = True  # 👈 補上此欄位（預設為 True 或 False）

class SellDeviceConfirmPayload(BaseModel):
    model: str = Field(..., description="设备型号或关键词，如：iPhone 13 128G 或 设备ID")
    price: float = Field(..., description="实际出售价格/成交价")
    payment_method: Optional[str] = Field(default="微信", description="收款方式")
    notes: Optional[str] = Field(default="二手销售", description="备注信息")

    sell_price: Optional[float] = Field(None, description="出售價格")
    device_id: Optional[int] = Field(default=None, description="設備 ID (與 sn 擇一即可)")
    sn: Optional[str] = Field(default=None, description="設備串號/IMEI (與 device_id 擇一即可)")
    customer_name: Optional[str] = Field(default=None, description="客戶姓名")
    customer_phone: Optional[str] = Field(default=None, description="客戶電話")
    spec: Optional[str] = Field(default=None, description="設備規格")
    quantity: Optional[int] = Field(default=1, description="數量")

class DeviceItem(BaseModel):
    model_name: str
    imei: str
    price: float

class SalesDetailResponse(BaseModel):
    id: int
    order_sn: str
    status: int  # 1: completed, 2: returned
    partner_name: str
    partner_phone: str
    total_amount: float
    created_at: str
    devices: List[DeviceItem]

class ReturnSalesRequest(BaseModel):
    id: int

class UpdateStatusRequest(BaseModel):
    id: int
    status: StockStatusEnum  # FastAPI 自動驗證傳入的值是否符合 1, 2, 3, 4