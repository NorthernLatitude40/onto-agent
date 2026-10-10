# src/api/v1/endpoints/inventory_device_api.py
"""
Device management endpoints - handles device inventory operations
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, case, or_, select, update, desc, asc
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from datetime import datetime, date, time as dt_time, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import get_db, get_db_async
from src.service.inventory_service import InventoryService
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from src.common.dict import ShopRole
from src.model.models import FinancialRecord
from src.model.inventory_model import InventoryModel as Inventory
from src.model.user_model import UserModel
from src.model.shop_model import ShopModel
from src.model.staff_model import StaffModel
from src.model.order_model import OutboundOrderModel as OutboundOrder
from src.model.schema import CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload
from src.model.partner_model import Partner
from src.model.models import FinancialRecord
from src.model.order_model import OutboundOrderModel
from src.model.order_item_model import OutboundOrderItem
from src.model.inventory_schema import CreateOutboundOrderPayload
from src.model.inventory_model import InventoryModel
from src.model.device_models import DeviceModel, DeviceModelAttribute
from src.api.auth_api import get_current_user, create_access_token
from src.common.exceptions import BusinessException
from src.config.config import settings
from src.dependencies.permissions import allow_shop_manager, allow_shop_staff
from src.model.clark_schema import StaffResponse
from src.model.dashboard_schema import DashboardOverviewResponse
from src.common.i18n import ErrorCode, get_i18n_message
from src.common.redis_client import redis_client
from src.model.inventory_schema import StockListResponse, SellDeviceResponse, AddDeviceConfirmPayload, CreatePurchaseOrderPayload, ReturnSalesRequest
from src.api.auth_api import get_current_staff
from src.common.generate_sn import generate_sn
from src.model.inventory_schema import UpdateStatusRequest, SellDeviceConfirmPayload
from src.common.dict import StockStatusEnum, PaymentStatusEnum

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/device/add", summary="確認設備入庫落庫")
async def confirm_add_device(
    payload: AddDeviceConfirmPayload,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    確認設備入庫落庫：
    - 更新庫存狀態 (status=2: 已入庫)
    - 記錄財務支出 (FinancialRecord)
    - 更新設備屬性
    """
    shop_id = current_staff.shop_id
    device_sn = payload.device_sn
    
    try:
        # 1. 查詢設備
        device = db.query(InventoryModel).filter(
            InventoryModel.device_sn == device_sn,
            InventoryModel.shop_id == shop_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="設備不存在")
        
        # 2. 更新庫存狀態為已入庫 (status=2)
        device.status = StockStatusEnum.IN_STOCK.value
        device.purchase_price = payload.purchase_price
        device.model_id = payload.model_id
        device.color = payload.color
        device.storage = payload.storage
        
        # 3. 記錄財務支出 (進貨成本)
        financial_record = FinancialRecord(
            shop_id=shop_id,
            amount=-payload.purchase_price,  # 負值表示支出
            category="purchase",
            description=f"進貨: {device_sn}",
            created_at=datetime.now()
        )
        db.add(financial_record)
        
        db.commit()
        return {"message": "入庫成功", "device_id": device.id}
    
    except Exception as e:
        db.rollback()
        logger.exception("【API 錯誤】設備確認入庫失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"入庫失敗: {str(e)}"
        )

class DetailedDeviceItem(BaseModel):
    device_sn: str = Field(..., description="設備序列號")
    model_id: int = Field(..., description="機型 ID")
    color: Optional[str] = Field(None, description="顏色")
    storage: Optional[str] = Field(None, description="儲存容量")
    purchase_price: Decimal = Field(..., description="進貨價格")

class CreateDetailedPurchasePayload(BaseModel):
    items: List[DetailedDeviceItem]

@router.post("/device/add-detailed", summary="確認二手機詳細資訊入庫落庫")
async def confirm_add_detailed_device(
    payload: CreateDetailedPurchasePayload,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    批量確認二手機詳細資訊入庫落庫：
    - 更新多個設備的庫存狀態 (status=2: 已入庫)
    - 記錄財務支出 (FinancialRecord)
    """
    shop_id = current_staff.shop_id
    
    try:
        for item in payload.items:
            # 查詢設備
            device = db.query(InventoryModel).filter(
                InventoryModel.device_sn == item.device_sn,
                InventoryModel.shop_id == shop_id
            ).first()
            
            if not device:
                raise HTTPException(status_code=404, detail=f"設備 {item.device_sn} 不存在")
            
            # 更新庫存狀態為已入庫 (status=2)
            device.status = StockStatusEnum.IN_STOCK.value
            device.purchase_price = item.purchase_price
            device.model_id = item.model_id
            device.color = item.color
            device.storage = item.storage
        
        db.commit()
        return {"message": "批量入庫成功", "count": len(payload.items)}
    
    except Exception as e:
        db.rollback()
        logger.exception("【API 錯誤】詳細設備確認入庫失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"入庫失敗: {str(e)}"
        )

@router.get("/device/options", summary="獲取機型與屬性字典")
async def get_device_options(db: AsyncSession = Depends(get_db_async)):
    """
    獲取所有機型及其屬性 (顏色、儲存容量) 的字典資料
    用於前端下拉選單
    """
    try:
        # 1. 查詢所有機型
        models = await db.execute(
            select(DeviceModel.id, DeviceModel.name)
            .order_by(DeviceModel.name)
        )
        model_list = models.scalars().all()
        
        # 2. 查詢所有全域通用屬性 (model_id 為 None 或 0)
        global_attrs = await db.execute(
            select(DeviceModelAttribute)
            .filter(
                or_(
                    DeviceModelAttribute.model_id == None,  # noqa: E711
                    DeviceModelAttribute.model_id == 0
                )
            )
            .order_by(DeviceModelAttribute.attribute_type, DeviceModelAttribute.value)
        )
        global_attrs_list = global_attrs.scalars().all()
        
        # 3. 查詢所有機型特定屬性
        model_specific_attrs = await db.execute(
            select(DeviceModelAttribute)
            .filter(
                DeviceModelAttribute.model_id != None,  # noqa: E711
                DeviceModelAttribute.model_id != 0
            )
            .order_by(DeviceModelAttribute.model_id, DeviceModelAttribute.attribute_type, DeviceModelAttribute.value)
        )
        model_specific_attrs_list = model_specific_attrs.scalars().all()
        
        # 4. 构建响应数据
        response = {
            "models": [{"id": m.id, "name": m.name} for m in model_list],
            "global_attributes": {
                "colors": [],
                "storages": []
            },
            "model_specific_attributes": {}
        }
        
        # 分类全局属性
        for attr in global_attrs_list:
            if attr.attribute_type == "color":
                response["global_attributes"]["colors"].append(attr.value)
            elif attr.attribute_type == "storage":
                response["global_attributes"]["storages"].append(attr.value)
        
        # 分类机型特定属性
        for attr in model_specific_attrs_list:
            if attr.model_id not in response["model_specific_attributes"]:
                response["model_specific_attributes"][attr.model_id] = {
                    "colors": [],
                    "storages": []
                }
            
            if attr.attribute_type == "color":
                response["model_specific_attributes"][attr.model_id]["colors"].append(attr.value)
            elif attr.attribute_type == "storage":
                response["model_specific_attributes"][attr.model_id]["storages"].append(attr.value)
        
        return response
    
    except Exception as e:
        logger.exception("【API 錯誤】獲取機型屬性字典失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}"
        )
