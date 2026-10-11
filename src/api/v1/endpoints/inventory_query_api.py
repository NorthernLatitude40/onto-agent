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

@router.get("/list1", response_model=StockListResponse, summary="獲取當前門店的設備庫存列表")
def get_inventory_list1(
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

# ------------------------------------------------------------------
# 2. 接口实现：GET /api/v1/shop/inventory/list
# ------------------------------------------------------------------
# 注意：把参数 query 中的 status 改名为 stock_status，避免与 fastapi.status 模块重名冲突！
@router.get("/list", response_model=StockListResponse, summary="獲取當前門店的設備庫存列表")
def get_inventory_list(
    stock_status: Optional[int] = Query(None, description="庫存狀態: 1-在庫, 2-已售, 3-退貨等"),
    category: Optional[int] = Query(None, description="分類篩選: 1-新機, 2-二手機"),
    keyword: Optional[str] = Query(None, description="模糊搜尋：機型名稱或串號/SN/IMEI"),
    sort_by: Optional[str] = Query(None, description="排序欄位，例如: 'stock_age' 或 'created_at'"),
    sort_order: Optional[str] = Query("desc", description="排序順序: 'asc' 或 'desc'"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(20, ge=1, le=100, description="每頁筆數"),
    db: Session = Depends(get_db),
    # 🌟 核心重構：直接注入依賴，驗證身分並獲取當前員工
    current_staff: StaffModel = Depends(allow_shop_staff) 
):
    """
    獲取當前門店下的設備庫存列表（支持分頁、狀態、分類、關鍵字檢索與動態排序）
    """
    # 1. 直接從 current_staff 中安全獲取當前請求的 shop_id
    shop_id = current_staff.shop_id

    # 2. 基礎查詢：過濾當前門店的數據
    query = db.query(InventoryModel).filter(InventoryModel.shop_id == shop_id)

    # 3. 按狀態篩選
    if stock_status is not None:
        query = query.filter(InventoryModel.status == stock_status)

    # 4. 按分類篩選 (1: 新機, 2: 二手機)
    if category is not None:
        query = query.filter(InventoryModel.category == category)

    # 5. 按關鍵字檢索 (過濾空字串、"undefined" 與 "null")
    if keyword and keyword.strip() and keyword.strip().lower() not in ["undefined", "null"]:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                InventoryModel.title.ilike(kw),
                InventoryModel.sn_code.ilike(kw)
            )
        )

    # 6. 計算符合條件的總筆數
    total = query.count()

    # 7. 🌟 動態排序邏輯 (Dynamic Sorting)
    order_direction = sort_order.lower() if sort_order else "desc"

    if sort_by == "stock_age":
        # 💡 庫齡邏輯：庫齡 = 當前時間 - 入庫時間(in_stock_time)
        # 庫齡越長 (desc) -> 入庫時間越早 (asc)
        # 庫齡越短 (asc)  -> 入庫時間越晚 (desc)
        if order_direction == "asc":
            query = query.order_by(desc(InventoryModel.in_stock_time))
        else:
            query = query.order_by(asc(InventoryModel.in_stock_time))
    else:
        # 預設按創建時間排序
        if order_direction == "asc":
            query = query.order_by(asc(InventoryModel.created_at))
        else:
            query = query.order_by(desc(InventoryModel.created_at))

    # 8. 分頁切片
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 9. 遵循 Bare Payload 規範或 StockListResponse 結構返回
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

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

@router.get("/inventory/detail1/{target_id}")
async def get_inventory_detail1(
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

@router.get("/inventory/detail/{target_id}")
async def get_inventory_detail(
    target_id: str,
    x_shop_id: Optional[str] = Header(None, alias="X-Shop-Id"),
    db: AsyncSession = Depends(get_db_async)
):
    """獲取設備詳情 (支援用數字 ID 或序列號/IMEI 查詢)"""
    
    stmt = select(InventoryModel)
    
    # 支持主鍵 ID 或 SN 號查詢
    if target_id.isdigit():
        stmt = stmt.where(or_(InventoryModel.id == int(target_id), InventoryModel.sn_code == target_id))
    else:
        stmt = stmt.where(InventoryModel.sn_code == target_id)

    if x_shop_id:
        stmt = stmt.where(InventoryModel.shop_id == int(x_shop_id))

    result = await db.execute(stmt)
    device = result.scalars().first()

    if not device:
        raise HTTPException(status_code=404, detail="未找到該設備資料")

    # 查詢供應商資訊 (若有關聯 supplier_id)
    supplier_name, supplier_phone = "未知供應商", "-"
    if device.supplier_id:
        p_stmt = select(Partner).where(Partner.id == device.supplier_id)
        p_res = await db.execute(p_stmt)
        supplier = p_res.scalars().first()
        if supplier:
            supplier_name = supplier.name or supplier_name
            supplier_phone = supplier.phone or supplier_phone

    return {
        "code": 200,
        "msg": "success",
        "data": {
            "id": device.id,
            "sn_code": device.sn_code,
            "title": device.title,
            "spec": device.spec,
            "category": device.category,
            "purchase_price": float(device.purchase_price or 0.0),
            "selling_price": float(device.selling_price or 0.0),
            "stock_quantity": device.stock_quantity,
            "status": int(device.status),  # 回傳數字 1, 2, 3, 4
            "supplier_name": supplier_name,
            "supplier_phone": supplier_phone,
            "in_stock_time": device.in_stock_time.strftime("%Y-%m-%d %H:%M:%S") if device.in_stock_time else "",
            "remark": device.remark
        }
    }

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
