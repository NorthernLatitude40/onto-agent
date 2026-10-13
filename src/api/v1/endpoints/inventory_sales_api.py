# src/api/v1/endpoints/inventory_sales_api.py
"""
Sales management endpoints - handles sales order creation and processing
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

@router.post("/create", summary="建立銷售單據")
def create_outbound_order(
    payload: CreateOutboundOrderPayload,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    建立銷售單據：
    - auto_deliver=True: 現場現貨交易，一步完成（建單 + 扣庫存 + 記財務收入）
    - auto_deliver=False: 預訂/待出庫，僅生成待交貨訂單 (status=1)
    """
    shop_id = current_staff.shop_id
    total_amount = Decimal("0.00")
    total_profit = Decimal("0.00")  # 初始化總毛利
    inventory_ids = [item.inventory_id for item in payload.items]

    if not inventory_ids:
        raise HTTPException(status_code=400, detail="請至少選擇一項商品")

    try:
        # 建立價格映射字典 {inventory_id: Decimal(sale_price)}
        price_map = {item.inventory_id: Decimal(str(item.sale_price)) for item in payload.items}

        # ---------------------------------------------------------
        # 1. 查詢庫存並加【行鎖】(with_for_update) 防併發超賣
        # ---------------------------------------------------------
        inventories = (
            db.query(InventoryModel)
            .filter(
                InventoryModel.id.in_(inventory_ids), 
                InventoryModel.shop_id == shop_id,
            )
            .with_for_update()  # 正確加鎖位置
            .all()
        )

        # 檢查數量是否匹配
        if len(inventories) != len(inventory_ids):
            raise HTTPException(status_code=400, detail="部分設備不存在或不屬於當前門店")

        # ---------------------------------------------------------
        # 2. 驗證庫存狀態 (僅允許已入庫 status=2)
        # ---------------------------------------------------------
        for inv in inventories:
            if inv.status != StockStatusEnum.IN_STOCK.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"設備 {inv.title} 狀態不正確 (當前: {inv.status}, 須為已入庫: {StockStatusEnum.IN_STOCK.value})"
                )

        # ---------------------------------------------------------
        # 3. 建立銷售單據
        # ---------------------------------------------------------
        order_sn = generate_sn(db, shop_id, "outbound_order", prefix="SO")
        
        outbound_order = OutboundOrder(
            shop_id=shop_id,
            order_sn=order_sn,
            customer_id=payload.customer_id,
            payment_status=PaymentStatusEnum.PAYED.value if payload.auto_deliver else PaymentStatusEnum.PAYING.value,
            created_at=datetime.now(),
        )
        db.add(outbound_order)
        db.flush()  # 获取 order_id

        # ---------------------------------------------------------
        # 4. 建立銷售明細 (OutboundOrderItem)
        # ---------------------------------------------------------
        for inv in inventories:
            sale_price = price_map[inv.id]
            
            # 計算毛利: 銷售價 - 進貨價
            profit = sale_price - Decimal(str(inv.purchase_price)) if inv.purchase_price else sale_price
            total_profit += profit
            
            order_item = OutboundOrderItem(
                outbound_order_id=outbound_order.id,
                inventory_id=inv.id,
                selling_price=sale_price,
                purchase_price=Decimal(str(inv.purchase_price)) if inv.purchase_price else Decimal("0.00"),
                profit=profit,
            )
            db.add(order_item)
            total_amount += sale_price
        
        # ---------------------------------------------------------
        # 5. auto_deliver=True: 立即交貨 (扣庫存 + 記財務收入)
        # ---------------------------------------------------------
        if payload.auto_deliver:
            outbound_order.payment_status = 2  # 已完成
            
            for inv in inventories:
                # 更新庫存狀態為已出售 (status=5)
                inv.status = StockStatusEnum.SOLD.value
                db.add(inv)
            
            # 記錄財務收入
            financial_record = FinancialRecord(
                shop_id=shop_id,
                amount=total_amount,
                category="sale",
                remark=f"銷售單: {order_sn}",
                record_time=datetime.now()
            )
            db.add(financial_record)
        
        db.commit()
        return {
            "order_id": outbound_order.id,
            "order_sn": order_sn,
            "total_amount": str(total_amount),
            "total_profit": str(total_profit),
            "status": outbound_order.payment_status
        }
    
    except Exception as e:
        db.rollback()
        logger.exception("【API 錯誤】建立銷售單據失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"建單失敗: {str(e)}"
        )

@router.post("/device/sell", summary="確認設備出售")
async def confirm_sell_device(
    payload: SellDeviceConfirmPayload,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    確認設備出售：
    - 更新庫存狀態 (status=5: 已出售)
    - 記錄財務收入 (FinancialRecord)
    """
    shop_id = current_staff.shop_id
    
    try:
        # 查詢設備
        device = db.query(InventoryModel).filter(
            InventoryModel.id == payload.device_id,
            InventoryModel.shop_id == shop_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="設備不存在")
        
        # 更新庫存狀態為已出售 (status=5)
        device.status = StockStatusEnum.SOLD.value
        
        # 記錄財務收入
        financial_record = FinancialRecord(
            shop_id=shop_id,
            amount=payload.price,
            category="sale",
            remark=f"銷售: {device.sn_code or device.title}",
            record_time=datetime.now()
        )
        db.add(financial_record)
        
        db.commit()
        return {"message": "出售成功", "inventory_id": device.id}
    
    except Exception as e:
        db.rollback()
        logger.exception("【API 錯誤】確認設備出售失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"出售失敗: {str(e)}"
        )

@router.post("/refund", summary="辦理銷售退貨")
def refund_outbound_order(
    payload: ReturnSalesRequest,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    办理銷售退貨：
    - 更新訂單狀態 (status=3: 已退貨)
    - 更新庫存狀態 (status=6: 已退貨)
    - 記錄財務調整 (FinancialRecord)
    """
    shop_id = current_staff.shop_id
    order_id = payload.order_id
    
    try:
        # 查詢訂單
        order = db.query(OutboundOrderModel).filter(
            OutboundOrderModel.id == order_id,
            OutboundOrderModel.shop_id == shop_id
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="訂單不存在")
        
        # 查詢訂單明細
        items = db.query(OutboundOrderItem).filter(
            OutboundOrderItem.order_id == order_id
        ).all()
        
        if not items:
            raise HTTPException(status_code=400, detail="訂單無商品明細")
        
        # 更新訂單狀態為已退貨 (status=3)
        order.status = 3
        
        # 更新庫存狀態為已退貨 (status=6)
        print(f"DEBUG: About to update {len(items)} items")
        for item in items:
            print(f"DEBUG: Processing item with inventory_id={item.inventory_id}")
            inventory = db.query(InventoryModel).filter(
                InventoryModel.id == item.inventory_id,
                InventoryModel.shop_id == shop_id
            ).first()
            
            print(f"DEBUG: Found inventory: {inventory}")
            if inventory:
                print(f"DEBUG: Before update - inventory.status={inventory.status}")
                inventory.status = StockStatusEnum.RETURNED.value
                print(f"DEBUG: After update - inventory.status={inventory.status}")
        
        # 記錄財務調整 (退款)
        financial_record = FinancialRecord(
            shop_id=shop_id,
            amount=-sum(item.sale_price for item in items),  # 負值表示退款
            category="refund",
            remark=f"退貨: {order.order_sn}",
            record_time=datetime.now()
        )
        db.add(financial_record)
        
        db.commit()
        return {"message": "退貨成功", "order_id": order.id}
    
    except Exception as e:
        db.rollback()
        logger.exception("【API 錯誤】辦理銷售退貨失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"退貨失敗: {str(e)}"
        )
