# src/api/dashboard_api.py
import time
import uuid
import logging
import json
import re
import hashlib
import ast
import jwt
import httpx
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, desc
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from datetime import datetime, date, time as dt_time, timedelta
from decimal import Decimal

from src.common.database import get_db # 获取数据库连接
from src.service.inventory_service import InventoryService
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from src.core.shop_agent.system import ShopAgentSystem
from src.common.dict import ShopRole
from src.model.models import FinancialRecord
from src.model.inventory_model import InventoryModel as Inventory
from src.model.user_model import UserModel
from src.model.shop_model import ShopModel
from src.model.staff_model import StaffModel
from src.model.order_model import OutboundOrderModel as OutboundOrder
from src.model.schema import  CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload
from src.model.partner_model import Partner
from src.model.models import (
    FinancialRecord
)
from src.model.order_model import OutboundOrderModel
from src.model.order_item_model import OutboundOrderItem
from src.model.inventory_schema import CreateOutboundOrderPayload
from src.model.inventory_model import InventoryModel
from src.api.auth_api import get_current_user, create_access_token
from src.common.exceptions import BusinessException
from src.config.config import settings
from src.dependencies.permissions import allow_shop_manager, allow_shop_staff
from src.model.clark_schema import StaffResponse
from src.model.dashboard_schema import DashboardOverviewResponse
from src.common.i18n import ErrorCode, get_i18n_message
from src.common.redis_client import redis_client
from src.model.inventory_schema import StockListResponse, SellDeviceResponse, AddDeviceConfirmPayload, CreatePurchaseOrderPayload
from src.api.auth_api import get_current_staff   # 直連 staff 的驗證依賴

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/device/add", summary="確認設備入庫落庫")
async def confirm_add_device(
    payload: CreatePurchaseOrderPayload, 
    db: Session = Depends(get_db),
    # 提取請求頭裡的 X-Shop-Id
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id")
):
    """
    前端提交待入庫單據時調用的接口：
    1. 寫入 inventory 表（根據 items 中的機型與串號列表批量落庫）
    2. 在 financial_record 表創建一筆對應的採購支出流水 (type=2)
    """
    # 1. 檢驗 shop_id
    if not x_shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="缺少必要參數：請求頭中未包含 X-Shop-Id"
        )
    
    # 2. 生成唯一請求簽名 (Hash Key) 防止重複提交
    raw_str = f"add_{payload.supplier_phone}_{payload.total_amount}_{x_shop_id}"
    lock_key = f"lock:device_add:{hashlib.md5(raw_str.encode()).hexdigest()}"

    # 嘗試向 Redis 獲取鎖 (ex=5 表示 5 秒內防重複提交)
    is_locked = redis_client.set(lock_key, "locked", ex=5, nx=True)

    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請勿重複提交！正在處理中..."
        )

    try:
        # 判斷單據狀態 (1-待驗收入庫，2-已驗收入庫)
        inventory_status = 1 if payload.status == "pending" else 2

        created_devices = []

        # 3. 遍歷 items 批量創建設備庫存記錄
        for item in payload.items:
            # 若傳入串號列表，按串號逐台建庫存；若無串號，至少建一條記錄
            serials_to_process = item.serials if item.serials else [""]

            for sn in serials_to_process:
                new_device = InventoryModel(
                    title=item.model_name,
                    sn_code=sn if sn else None,
                    purchase_price=item.cost_price,
                    category=2,                           # 2 - 二手機
                    status=inventory_status,             # 1 - 待入庫/在庫
                    supplier_id=payload.partner_id,      # 往來單位 ID (客戶/供應商)
                    created_by=payload.operator_id,    # 經手人 ID
                    shop_id=x_shop_id,
                    remark=f"來源電話: {payload.supplier_phone}"
                )
                db.add(new_device)
                created_devices.append(new_device)

        # 提前刷新以取得生成的設備 ID (若需關聯)
        db.flush()

        # 4. 生成財務支出流水單號與記錄 (總金額採購支出)
        record_sn = f"EXP_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"
        financial_record = FinancialRecord(
            record_sn=record_sn,
            type=2,                                       # 1-收入，2-支出
            category="二手回收",                           # 科目
            amount=payload.total_amount,                  # 支出總金額
            profit=0.0,                                   # 採購進貨不計入利潤/虧損
            business_type=1,                              # 關聯業務：1-手機設備
            business_id=created_devices[0].id if created_devices else None, # 綁定首台設備 ID
            payment_method="微信",                         # 預設支付方式
            remark=f"採購入庫單據 (聯繫電話: {payload.supplier_phone}, 共 {len(created_devices)} 台)",
            shop_id=x_shop_id
        )
        db.add(financial_record)

        # 5. 統一提交事務
        db.commit()

        return {
            "code": 200,
            "message": "設備單據成功提交並記帳！",
            "data": {
                "record_sn": record_sn,
                "total_amount": payload.total_amount,
                "device_count": len(created_devices),
                "status": payload.status
            }
        }

    except Exception as e:
        db.rollback()
        redis_client.delete(lock_key)
        logger.exception("【API 錯誤】設備確認入庫失敗:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"入庫失敗: {str(e)}"
        )

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
    inventory_ids = [item.inventory_id for item in payload.items]

    # 1. 檢查庫存狀態
    inventories = (
        db.query(InventoryModel)
        .filter(InventoryModel.id.in_(inventory_ids), InventoryModel.shop_id == shop_id)
        .all()
    )

    if len(inventories) != len(inventory_ids):
        raise HTTPException(status_code=400, detail="部分設備不存在或不屬於當前門店")

    for inv in inventories:
        if inv.status != 1:  # 1: 在庫
            raise HTTPException(status_code=400, detail=f"設備 (SN: {inv.sn_code}) 非在庫狀態")

    try:
        price_map = {item.inventory_id: item.sale_price for item in payload.items}
        for inv in inventories:
            total_amount += price_map[inv.id]

        outbound_no = f"OUT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_staff.id}"
        # order_status = 2 if payload.auto_deliver else 1  # 2: 已完成, 1: 待出庫
        is_auto_deliver = getattr(payload, 'auto_deliver', True)
        order_status = 2 if is_auto_deliver else 1

        # 2. 生成出貨主單
        order = OutboundOrderModel(
            order_sn=outbound_no,
            shop_id=shop_id,
            customer_id=payload.customer_id,
            created_by=current_staff.id,
            total_amount=total_amount,
            payment_status=order_status,
            remark=payload.remark
        )
        db.add(order)
        db.flush()

        # 3. 建立出貨明細
        for inv in inventories:
            order_item = OutboundOrderItem(
                outbound_order_id=order.id,
                inventory_id=inv.id,
                selling_price=price_map[inv.id]
            )
            db.add(order_item)

            # 若直接交貨，更新庫存狀態 (2: 已售出)
            if payload.auto_deliver:
                inv.status = 2

        fin_sn = f"FIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_staff.id}"

        # 4. 若直接交貨，生成財務收入紀錄
        if payload.auto_deliver:
            financial_record = FinancialRecord(
                shop_id=shop_id,
                type=1,  # 1: 收入
                record_sn=fin_sn,
                amount=total_amount,
                category="sales",
                business_id=order.id,
                created_by=current_staff.id,
                remark=f"銷售單直接結算: {outbound_no}"
            )
            db.add(financial_record)

        db.commit()
        return {
            "code": 200,
            "message": "開單成功" if payload.auto_deliver else "預訂單建立成功，等待出庫",
            "outbound_no": outbound_no,
            "id": order.id
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"開單失敗: {str(e)}")


# ====================================================
# 2. 确认出售 API (请求体 & 路由接口)
# ====================================================

class SellDeviceConfirmPayload(BaseModel):
    model: str = Field(..., description="设备型号或关键词，如：iPhone 13 128G 或 设备ID")
    price: float = Field(..., description="实际出售价格/成交价")
    payment_method: Optional[str] = Field(default="微信", description="收款方式")
    notes: Optional[str] = Field(default="二手销售", description="备注信息")

import re

# 1. 定义指代词黑名单（正则表达式）
PRONOUN_PATTERN = re.compile(
    r"^(刚才|上|这|那|刚刚|那个|这台|那台|上一台|刚才这台|刚才那台|它|把它)+(机器|手机|设备|产品|东西)?$"
)

def clean_device_model(model_str: str, db_session, shop_id: int) -> str:
    """后端防御：清洗 LLM 传过来的型号，如果是代词则自动查找最近一条库存设备"""
    if not model_str:
        return ""

    # 去掉前后空格
    cleaned = model_str.strip()

    # 如果命中黑名单（比如：上一台、刚才这台机器）
    if PRONOUN_PATTERN.match(cleaned) or cleaned in ["UNKNOWN", "未知"]:
        # 🟢 自动去数据库查最近入库的一台【在库】设备
        latest_inventory = (
            db_session.query(InventoryModel)
            .filter(InventoryModel.shop_id == shop_id, InventoryModel.status == 1) # 1: 在库
            .order_by(InventoryModel.created_at.desc())
            .first()
        )
        
        if latest_inventory:
            # 用真实设备的名称替换掉代词！
            return latest_inventory.title
        else:
            raise ValueError("没有找到最近可出售的在库设备")

    return cleaned


@router.post(
    "/device/sell",
    response_model=SellDeviceResponse,  # 🌟 直接指定 Bare Payload 的 Pydantic Response 模型
    status_code=status.HTTP_200_OK,
    summary="确认设备出售出库",
)
async def confirm_sell_device(
    request: Request,
    payload: SellDeviceConfirmPayload,
    db: Session = Depends(get_db),
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
):
    # ---------------------------------------------------------
    # 1. Header 校验：缺失直接抛出 BusinessException
    # ---------------------------------------------------------
    if not x_shop_id:
        raise BusinessException(
            code=ErrorCode.MISSING_SHOP_ID,
            detail="缺少必要参数：请求头中未包含 X-Shop-Id",
            status_code=status.HTTP_400_BAD_REQUEST,
            type_url="https://api.yourdomain.com/errors/missing-shop-id",
        )

    real_model = clean_device_model(payload.model, db, x_shop_id)

    # ---------------------------------------------------------
    # 2. 幂等防重锁 (结合店铺隔离)
    # ---------------------------------------------------------
    raw_str = f"sell_{x_shop_id}_{real_model}_{payload.price}_{payload.notes}"
    lock_key = f"lock:device_sell:{hashlib.md5(raw_str.encode()).hexdigest()}"
    is_locked = redis_client.set(lock_key, "locked", ex=5, nx=True)

    if not is_locked:
        raise BusinessException(
            code=ErrorCode.DUPLICATE_REQUEST,
            detail="请勿重复提交！正在处理中...",
            status_code=status.HTTP_400_BAD_REQUEST,
            type_url="https://api.yourdomain.com/errors/duplicate-request",
        )

    try:
        # ---------------------------------------------------------
        # 3. 🛡️ 悲观排他锁 (SELECT ... FOR UPDATE) 防并发超卖
        # ---------------------------------------------------------
        query = db.query(InventoryModel).filter(
            InventoryModel.status == 1,
            InventoryModel.shop_id == x_shop_id,
            InventoryModel.stock_quantity > 0,
        )

        if real_model.isdigit():
            query = query.filter(InventoryModel.id == int(real_model))
        else:
            query = query.filter(InventoryModel.title.ilike(f"%{real_model}%"))

        # 锁定选中行记录
        device = query.with_for_update().first()

        # 双重校验：避免排队等待锁出来后库存已被上一事务扣完
        if not device or device.stock_quantity <= 0:
            raise BusinessException(
                code=ErrorCode.DEVICE_NOT_FOUND_OR_SOLD,
                detail=f"未在库存中找到可售设备或已被抢先售出：'{real_model}'",
                status_code=status.HTTP_404_NOT_FOUND,
                type_url="https://api.yourdomain.com/errors/device-not-found",
            )

        # ---------------------------------------------------------
        # 4. 核心逻辑：计算金额与安全扣减库存
        # ---------------------------------------------------------
        cost_price = float(device.purchase_price or 0)
        sell_price = payload.price
        profit = sell_price - cost_price

        device.stock_quantity -= 1
        if device.stock_quantity <= 0:
            device.stock_quantity = 0
            device.status = 2  # 已出库

        # ---------------------------------------------------------
        # 5. 写入出库单、明细及财务流水
        # ---------------------------------------------------------
        order_sn = (
            f"OUT_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"
        )
        outbound_order = OutboundOrder(
            order_sn=order_sn,
            total_amount=sell_price,
            created_at=datetime.now(),
            shop_id=x_shop_id,
        )
        db.add(outbound_order)
        db.flush()

        order_item = OutboundOrderItem(
            outbound_order_id=outbound_order.id,
            inventory_id=device.id,
            quantity=1,
            purchase_price=cost_price,
            selling_price=sell_price,
            profit=profit,
        )
        db.add(order_item)

        financial_record = FinancialRecord(
            record_sn=f"INC_{order_sn}",
            type=1,
            category="手机销售",
            amount=sell_price,
            profit=profit,
            business_type=1,
            business_id=outbound_order.id,
            payment_method=payload.payment_method,
            remark=f"设备出售出库：{device.title} | 订单号:{order_sn}",
            shop_id=x_shop_id,
            device_sn_code=device.sn_code,
        )
        db.add(financial_record)

        # 提交事务并释放行锁
        db.commit()

        # ---------------------------------------------------------
        # 6. 🌟 Bare Payload 模式：直接返回 Schema 对象或裸字典
        # ---------------------------------------------------------
        return SellDeviceResponse(
            id=device.id,
            model=device.title,
            order_sn=order_sn,
            sell_price=sell_price,
            profit=profit,
        )

    except BusinessException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.exception("【系统错误】设备确认出售失败:")
        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            detail=f"服务器内部数据错误: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            type_url="https://api.yourdomain.com/errors/internal-server-error",
        )

    finally:
        redis_client.delete(lock_key)

# ------------------------------------------------------------------
# 2. 接口实现：GET /api/v1/shop/inventory/list
# ------------------------------------------------------------------
# 注意：把参数 query 中的 status 改名为 stock_status，避免与 fastapi.status 模块重名冲突！
@router.get("/list", response_model=StockListResponse, summary="獲取當前門店的設備庫存列表")
def get_inventory_list(
    stock_status: Optional[int] = Query(None, alias="status", description="庫存狀態: 1-在庫, 2-已售, 3-退貨等"),
    category: Optional[int] = Query(None, description="分類篩選: 1-新機, 2-二手機"),
    keyword: Optional[str] = Query(None, description="模糊搜尋：機型名稱或串號/SN/IMEI"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(20, ge=1, le=100, description="每頁筆數"),
    db: Session = Depends(get_db),
    # 🌟 核心重構：直接注入依賴，驗證身分並獲取當前員工
    current_staff: StaffModel = Depends(allow_shop_staff) 
):
    """
    獲取當前門店下的設備庫存列表（支持分頁、狀態、分類與關鍵字檢索）
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

    # 7. 排序與分頁切片
    items = (
        query.order_by(desc(InventoryModel.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 8. 遵循 Bare Payload 規範或 StockListResponse 結構返回
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

@router.get("/search_by_sn")
def search_inventory_by_sn(
    sn_code: str = Query(..., description="設備 IMEI 或 SN 碼"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_staff)
):
    """
    根據 SN 碼 / IMEI 查詢門店在庫設備
    """
    clean_sn = sn_code.strip()
    if not clean_sn:
        raise HTTPException(status_code=400, detail="請提供有效的 SN 或 IMEI 碼")

    # 1. 在庫存表/設備表中查詢對應的 SN/IMEI
    inventory = db.query(InventoryModel).filter(
        InventoryModel.shop_id == current_user.shop_id,
        InventoryModel.sn_code == clean_sn
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="未找到該 SN/IMEI 的設備")

    # 2. 獲取關聯的機型/商品資訊 (若有獨立 Product 表)
    product_title = inventory.title if hasattr(inventory, 'title') else "未知機型"
    if hasattr(inventory, 'product_id') and inventory.product_id:
        product = db.query(InventoryModel).filter(InventoryModel.id == inventory.product_id).first()
        if product:
            product_title = product.title or product.name

    # 3. 返回前端需要的設備詳情數據
    return {
        "id": inventory.id,
        "sn_code": inventory.sn_code,
        "product_id": getattr(inventory, 'product_id', None),
        "title": product_title,
        "status": inventory.status,  # 1: 在庫, 2: 已售出, 3: 報廢/維修中 等
        "cost_price": float(inventory.cost_price) if getattr(inventory, 'cost_price', None) else 0.0,
        "selling_price": float(inventory.selling_price) if getattr(inventory, 'selling_price', None) else 0.0,
        "retail_price": float(inventory.retail_price) if getattr(inventory, 'retail_price', None) else 0.0,
        "created_at": inventory.created_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(inventory, 'created_at', None) else None
    }