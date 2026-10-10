# src/api/v1/endpoints/inventory_query_api.py
"""
Inventory query endpoints - handles inventory listing and search operations
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

@router.get("/list", response_model=StockListResponse, summary="獲取當前門店的設備庫存列表")
def get_inventory_list(
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    獲取當前門店的設備庫存列表
    """
    shop_id = current_staff.shop_id
    
    try:
        # 查詢所有庫存 (僅顯示已入庫 status=2)
        inventories = (
            db.query(InventoryModel)
            .filter(
                InventoryModel.shop_id == shop_id,
                InventoryModel.status != StockStatusEnum.IN_STOCK.value
            )
            .all()
        )
        
        return {"items": inventories}
    except Exception as e:
        logger.exception("【API 錯誤】獲取庫存列表失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}"
        )

@router.get("/search_by_sn")
def search_inventory_by_sn(
    device_sn: str = Query(..., description="設備序列號"),
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    根據序列號查詢庫存
    """
    shop_id = current_staff.shop_id
    
    try:
        inventory = (
            db.query(InventoryModel)
            .filter(
                InventoryModel.device_sn == device_sn,
                InventoryModel.shop_id == shop_id
            )
            .first()
        )
        
        if not inventory:
            raise HTTPException(status_code=404, detail="設備不存在")
        
        return inventory
    except Exception as e:
        logger.exception("【API 錯誤】查詢庫存失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}"
        )

@router.get("/detail/{order_id}")
async def get_sales_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db_async),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    獲取銷售單據明細
    """
    shop_id = current_staff.shop_id
    
    try:
        # 查詢訂單
        order = await db.get(OutboundOrderModel, order_id)
        
        if not order or order.shop_id != shop_id:
            raise HTTPException(status_code=404, detail="訂單不存在")
        
        # 查詢訂單明細
        items = (
            await db.execute(
                select(OutboundOrderItem).where(OutboundOrderItem.outbound_order_id == order_id)
            )
        ).scalars().all()
        
        return {
            "order": order,
            "items": items
        }
    except Exception as e:
        logger.exception("【API 錯誤】獲取銷售單據明細失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}"
        )

@router.get("/inventory/detail/{target_id}")
async def get_inventory_detail(
    target_id: int,
    db: AsyncSession = Depends(get_db_async),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    獲取庫存明細
    """
    shop_id = current_staff.shop_id
    
    try:
        inventory = await db.get(InventoryModel, target_id)
        
        if not inventory or inventory.shop_id != shop_id:
            raise HTTPException(status_code=404, detail="庫存不存在")
        
        return inventory
    except Exception as e:
        logger.exception("【API 錯誤】獲取庫存明細失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}"
        )

@router.get("/device/options", summary="獲取機型與屬性字典")
async def get_device_options(db: AsyncSession = Depends(get_db_async)):
    """
    獲取所有機型與其屬性字典 (用於前端下拉選單)
    """
    try:
        # 查詢所有機型
        models = await db.execute(select(DeviceModel))
        device_models = models.scalars().all()
        
        # 查詢所有屬性
        attributes = await db.execute(select(DeviceModelAttribute))
        device_attributes = attributes.scalars().all()
        
        return {
            "models": [{"id": m.id, "name": m.name} for m in device_models],
            "attributes": [{"id": a.id, "name": a.name} for a in device_attributes]
        }
    except Exception as e:
        logger.exception("【API 錯誤】獲取機型與屬性字典失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}"
        )
