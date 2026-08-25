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
from sqlalchemy.orm import Session,  selectinload
from sqlalchemy import func, case, or_, select, update, desc, asc
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from datetime import datetime, date, time as dt_time, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import get_db, get_db_async # 获取数据库连接
from src.service.inventory_service import InventoryService
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
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
from src.api.auth_api import get_current_staff   # 直連 staff 的驗證依賴
from src.common.generate_sn import generate_sn
from src.model.inventory_schema import UpdateStatusRequest,SellDeviceConfirmPayload
from src.common.dict import StockStatusEnum, PaymentStatusEnum

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/device/add", summary="確認設備入庫落庫")
async def confirm_add_device(
    payload: CreatePurchaseOrderPayload, 
    db: Session = Depends(get_db),
    # 提取請求頭裡的 X-Shop-Id
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    前端提交待入庫單據時調用的接口：
    1. 自動補全或創建往來單位 (Partner)
    2. 寫入 inventory 表（根據 items 中的機型與串號列表批量落庫）
    3. 在 financial_record 表創建一筆對應的採購支出流水 (type=2)
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
        # ==================== 【新增邏輯】處理 Partner (客戶/供應商) ====================
        partner_id = payload.partner_id
        phone = (payload.supplier_phone or "").strip()
        name = (payload.supplier_name or "").strip()

        # 如果前端沒有傳 partner_id，且有提供手機號碼，進行查重或自動新建
        if not partner_id and phone:
            existing_partner = db.query(Partner).filter(Partner.phone == phone,  Partner.shop_id == int(x_shop_id)).first()
            if existing_partner:
                partner_id = existing_partner.id
            else:
                # 建立新 Partner（預設名稱若未提供則自動設為 "客戶_{手機後4碼}" 或 "未命名"）
                default_name = name if name else f"客戶_{phone[-4:] if len(phone) >= 4 else phone}"
                new_partner = Partner(
                    name=default_name,
                    phone=phone,
                    shop_id=x_shop_id,
                    type=2,  # 預設 2-供應商 (或依業務需求設為 3-二者皆是)
                    receivable_amount=0.00,
                    payable_amount=0.00,
                    remark="設備入庫時自動創建"
                )
                db.add(new_partner)
                db.flush()  # 刷入 DB 以獲取自動生成的 new_partner.id
                partner_id = new_partner.id
        # ==============================================================================

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
                    color=item.color,
                    storage=item.storage,
                    sn_code=sn if sn else None,
                    purchase_price=item.cost_price,
                    category=item.type,                          # 2 - 二手機
                    status=inventory_status,                     # 1 - 待入庫/在庫
                    supplier_id=partner_id,                      # 👈 寫入自動查詢/創建後拿到的 partner_id
                    created_by=current_staff.id,                 # 經手人 ID
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
                "partner_id": partner_id,                # 帶回最終綁定的 Partner ID
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

from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
import hashlib
import uuid
from datetime import datetime

# ==================== 1. 新的請求 Payload Schema ====================
class DetailedDeviceItem(BaseModel):
    model_name: str = Field(..., description="機型名稱")
    condition: Optional[str] = Field(None, description="成色 (例: 8新, 99新)")
    color: Optional[str] = Field(None, description="顏色 (例: 午夜色)")
    storage: Optional[str] = Field(None, description="內存 (例: 256GB)")
    version: Optional[str] = Field(None, description="版本 (例: 大陸國行)")
    battery: Optional[str] = Field(None, description="電池健康值 (例: 77%)")
    system: Optional[str] = Field(None, description="系統版本 (例: iOS 16)")
    network: Optional[str] = Field(None, description="網絡類型 (例: 全網通)")
    condition_detail: Optional[str] = Field(None, description="機況說明")
    imei: Optional[str] = Field(None, description="IMEI 碼")
    sn_code: Optional[str] = Field(None, description="SN 序列號")
    is_outof_warranty: bool = Field(True, description="是否已過保")
    cost_price: float = Field(0.00, description="單台成本價")

class CreateDetailedPurchasePayload(BaseModel):
    supplier_phone: Optional[str] = Field(None, description="聯繫電話/客戶電話")
    supplier_name: Optional[str] = Field(None, description="姓名/名稱")
    partner_id: Optional[int] = Field(None, description="往來單位 ID")
    total_amount: float = Field(..., description="採購總金額")
    status: str = Field("pending", description="單據狀態: pending-待驗收, completed-已入庫")
    items: List[DetailedDeviceItem] = Field(..., description="設備明細列表")


# ==================== 2. 新增的後端接口 ====================
@router.post("/device/add-detailed", summary="確認二手機詳細資訊入庫落庫")
async def confirm_add_detailed_device(
    payload: CreateDetailedPurchasePayload, 
    db: Session = Depends(get_db),
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    對應新版前端原型的入庫接口：
    1. 自動補全或創建往來單位 (Partner)
    2. 寫入 inventory 表（支援成色、顏色、內存、版本、電池、系統、網絡、機況、IMEI/SN、過保狀態）
    3. 在 financial_record 表創建一筆對應的採購支出流水 (type=2)
    """
    # 1. 檢驗 shop_id
    if not x_shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="缺少必要參數：請求頭中未包含 X-Shop-Id"
        )
    
    # 2. 防重複提交機制 (Redis Lock)
    raw_str = f"add_detailed_{payload.supplier_phone}_{payload.total_amount}_{x_shop_id}"
    lock_key = f"lock:device_add_detailed:{hashlib.md5(raw_str.encode()).hexdigest()}"

    is_locked = redis_client.set(lock_key, "locked", ex=5, nx=True)
    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請勿重複提交！正在處理中..."
        )

    try:
        # 3. 處理 Partner (客戶/供應商) 自動匹配或建立
        partner_id = payload.partner_id
        phone = (payload.supplier_phone or "").strip()
        name = (payload.supplier_name or "").strip()

        if not partner_id and phone:
            existing_partner = db.query(Partner).filter(
                Partner.phone == phone, 
                Partner.shop_id == int(x_shop_id)
            ).first()
            
            if existing_partner:
                partner_id = existing_partner.id
            else:
                default_name = name if name else f"客戶_{phone[-4:] if len(phone) >= 4 else phone}"
                new_partner = Partner(
                    name=default_name,
                    phone=phone,
                    shop_id=x_shop_id,
                    type=2,  # 供應商
                    receivable_amount=0.00,
                    payable_amount=0.00,
                    remark="設備入庫時自動創建"
                )
                db.add(new_partner)
                db.flush()
                partner_id = new_partner.id

        # 4. 判斷單據狀態 (1-待驗收入庫，2-已驗收入庫)
        inventory_status = 1 if payload.status == "pending" else 2
        created_devices = []

        # 5. 遍歷 items 批量創建設備詳細庫存記錄
        for item in payload.items:
            new_device = InventoryModel(
                title=item.model_name,
                sn_code=item.sn_code if item.sn_code else None,
                imei=item.imei if item.imei else None,             # 結構化寫入 IMEI
                purchase_price=item.cost_price,
                category=2,                                       # 2 - 二手機
                status=inventory_status,                          # 狀態
                supplier_id=partner_id,                           # 關聯供應商
                created_by=current_staff.id,                      # 經手人 ID
                shop_id=x_shop_id,
                
                # 規格資訊
                condition=item.condition,                         # 成色
                color=item.color,                                 # 顏色
                storage=item.storage,                             # 內存
                version=item.version,                             # 版本
                battery=item.battery,                             # 電池健康
                system_version=item.system,                       # 系統
                network=item.network,                             # 網絡
                condition_detail=item.condition_detail,           # 機況
                is_outof_warranty=item.is_outof_warranty,         # 是否過保
                
                remark=f"來源電話: {payload.supplier_phone}"       # 備註回歸乾淨的業務說明
            )
            db.add(new_device)
            created_devices.append(new_device)

        db.flush()

        # 6. 生成財務支出流水
        record_sn = f"EXP_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"
        financial_record = FinancialRecord(
            record_sn=record_sn,
            type=2,                                      # 2-支出
            category="二手回收",                          # 科目
            amount=payload.total_amount,                 # 支出總金額
            profit=0.0,
            business_type=1,                             # 1-手機設備
            business_id=created_devices[0].id if created_devices else None,
            payment_method="微信",
            remark=f"詳細設備採購入庫 (聯繫電話: {payload.supplier_phone}, 共 {len(created_devices)} 台)",
            shop_id=x_shop_id
        )
        db.add(financial_record)

        # 7. 提交事務
        db.commit()

        return {
            "code": 200,
            "message": "詳細設備單據成功提交並入庫！",
            "data": {
                "record_sn": record_sn,
                "partner_id": partner_id,
                "total_amount": payload.total_amount,
                "device_count": len(created_devices),
                "status": payload.status
            }
        }

    except Exception as e:
        db.rollback()
        redis_client.delete(lock_key)
        logger.exception("【API 錯誤】詳細設備確認入庫失敗:")
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
        # 2. 庫存狀態與數量雙重校驗 & 計算總金額與總毛利
        # ---------------------------------------------------------
        for inv in inventories:
            # 狀態檢查
            if inv.status != StockStatusEnum.IN_STOCK.value:
                raise BusinessException(
                    code=ErrorCode.DEVICE_NOT_FOUND_OR_SOLD,
                    detail=f"設備 (SN: {inv.sn_code or inv.id}) 非在庫狀態或已被售出",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    type_url="https://api.yourdomain.com/errors/device-not-found",
                )
            
            # 數量檢查
            if inv.stock_quantity <= 0:
                raise BusinessException(
                    code=ErrorCode.DEVICE_NOT_FOUND_OR_SOLD,
                    detail=f"設備 '{inv.title or inv.sn_code}' 庫存不足",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    type_url="https://api.yourdomain.com/errors/device-not-found",
                )

            # 累加總金額
            item_price = price_map.get(inv.id, Decimal("0.00"))
            cost_price = Decimal(str(inv.purchase_price or 0))
            
            total_amount += item_price
            total_profit += (item_price - cost_price)  # 正確累加單台毛利至總毛利

            # ---------------------------------------------------------
            # 3. 若為現貨直接交貨 (auto_deliver=True)，扣減庫存並改狀態
            # ---------------------------------------------------------
            if payload.auto_deliver:
                inv.stock_quantity -= 1
                if inv.stock_quantity <= 0:
                    inv.stock_quantity = 0
                    inv.status = StockStatusEnum.SOLD.value  # 設為已售出 (Status 3)

        # ---------------------------------------------------------
        # 4. 生成出貨主單
        # ---------------------------------------------------------
        outbound_no = f"OUT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_staff.id}"
        is_auto_deliver = getattr(payload, 'auto_deliver', True)
        order_status = 2 if is_auto_deliver else 1  # 2: 已完成, 1: 待出庫

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
        db.flush()  # 獲取 order.id

        # ---------------------------------------------------------
        # 5. 建立出貨明細
        # ---------------------------------------------------------
        for inv in inventories:
            order_item = OutboundOrderItem(
                outbound_order_id=order.id,
                inventory_id=inv.id,
                selling_price=price_map[inv.id]
            )
            db.add(order_item)

        # ---------------------------------------------------------
        # 6. 若為直接交貨，生成財務收入紀錄 (帶入總毛利)
        # ---------------------------------------------------------
        if is_auto_deliver:
            fin_sn = f"FIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_staff.id}"
            financial_record = FinancialRecord(
                shop_id=shop_id,
                type=1,  # 1: 收入
                record_sn=fin_sn,
                amount=total_amount,
                profit=total_profit,  # 正確傳入整單的總毛利
                category="sales",
                business_id=order.id,
                created_by=current_staff.id,
                remark=f"銷售單直接結算: {outbound_no}"
            )
            db.add(financial_record)

        db.commit()
        return {
            "code": 200,
            "message": "開單成功" if is_auto_deliver else "預訂單建立成功，等待出庫",
            "outbound_no": outbound_no,
            "id": order.id
        }

    except HTTPException:
        db.rollback()
        raise
    except BusinessException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"開單失敗: {str(e)}"
        )


# ====================================================
# 2. 确认出售 API (请求体 & 路由接口)
# ====================================================



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


def _build_outbound_order(
    shop_id: int,
    total_amount: Decimal,
    customer_id: Optional[int] = None,
    created_by: Optional[int] = None,
    payment_status: int = 2,  # 預設 2: 已完成
    remark: Optional[str] = None,
) -> OutboundOrderModel:
    """構建標準化的出貨主單實例 (補充完整欄位)"""
    outbound_no = f"OUT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    return OutboundOrderModel(
        order_sn=outbound_no,
        shop_id=shop_id,
        customer_id=customer_id,
        created_by=created_by,
        total_amount=total_amount,
        payment_status=payment_status,
        remark=remark,
    )


def _build_outbound_order_item(
    outbound_order_id: int,
    inventory_id: int,
    selling_price: Decimal,
    quantity: int = 1,
    purchase_price: Optional[Decimal] = None,
    profit: Optional[Decimal] = None,
) -> OutboundOrderItem:
    """構建標準化的出貨明細實例"""
    return OutboundOrderItem(
        outbound_order_id=outbound_order_id,
        inventory_id=inventory_id,
        selling_price=selling_price,
        quantity=quantity,
        purchase_price=purchase_price,
        profit=profit,
    )


def _build_financial_record(
    shop_id: int,
    amount: Decimal,
    profit: Decimal,
    business_id: int,
    created_by: Optional[int] = None,
    category: str = "sales",
    payment_method: Optional[str] = None,
    device_sn_code: Optional[str] = None,
    remark: Optional[str] = None,
) -> FinancialRecord:
    """構建標準化的財務流水紀錄 (補齊類型與擴展欄位)"""
    fin_sn = f"FIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    return FinancialRecord(
        shop_id=shop_id,
        type=1,  # 1: 收入
        record_sn=fin_sn,
        amount=amount,
        profit=profit,
        category=category,
        business_type=1,  # 銷售業務
        business_id=business_id,
        created_by=created_by,
        payment_method=payment_method,
        device_sn_code=device_sn_code,
        remark=remark,
    )

@router.post(
    "/device/sell",
    response_model=SellDeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="确认设备出售出库",
)
async def confirm_sell_device(
    request: Request,
    payload: SellDeviceConfirmPayload,
    db: Session = Depends(get_db),
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
):
    """
    單台設備快速出售 (無改動 API 傳參，補齊全量寫入欄位)
    """
    if not x_shop_id:
        raise BusinessException(
            code=ErrorCode.MISSING_SHOP_ID,
            detail="缺少必要参数：请求头中未包含 X-Shop-Id",
            status_code=status.HTTP_400_BAD_REQUEST,
            type_url="https://api.yourdomain.com/errors/missing-shop-id",
        )

    real_model = clean_device_model(payload.model, db, x_shop_id)

    # 冪等鎖
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
        # 1. 悲觀排他鎖
        query = db.query(InventoryModel).filter(
            InventoryModel.status == StockStatusEnum.IN_STOCK.value,
            InventoryModel.shop_id == x_shop_id,
            InventoryModel.stock_quantity > 0,
            InventoryModel.title.ilike(f"%{real_model}%")
        )
        device = query.with_for_update().first()

        if not device or device.stock_quantity <= 0:
            raise BusinessException(
                code=ErrorCode.DEVICE_NOT_FOUND_OR_SOLD,
                detail=f"未在库存中找到可售设备或已被抢先售出：'{real_model}'",
                status_code=status.HTTP_404_NOT_FOUND,
                type_url="https://api.yourdomain.com/errors/device-not-found",
            )

        # 2. 金額與庫存扣減 (改用 Decimal 保持精度一致)
        cost_price = Decimal(str(device.purchase_price or 0))
        sell_price = Decimal(str(payload.price))
        profit = sell_price - cost_price

        device.stock_quantity -= 1
        if device.stock_quantity <= 0:
            device.stock_quantity = 0
            device.status = StockStatusEnum.SOLD.value

        # 3. 補全寫入 OutboundOrder (對齊 /create 補齊 customer_id, payment_status, remark)
        outbound_order = _build_outbound_order(
            shop_id=x_shop_id,
            total_amount=sell_price,
            customer_id=getattr(payload, 'customer_id', None),  # 若前端有帶可擴充，無帶為 None
            created_by=getattr(payload, 'staff_id', None),
            payment_status=2,  # 2: 已完成
            remark=payload.notes or f"單台設備出售: {device.title}",
        )
        db.add(outbound_order)
        db.flush()

        # 4. 補全寫入 OutboundOrderItem
        order_item = _build_outbound_order_item(
            outbound_order_id=outbound_order.id,
            inventory_id=device.id,
            selling_price=sell_price,
            quantity=1,
            purchase_price=cost_price,
            profit=profit,
        )
        db.add(order_item)

        # 5. 補全寫入 FinancialRecord (對齊 /create 補齊 created_by, category)
        financial_record = _build_financial_record(
            shop_id=x_shop_id,
            amount=sell_price,
            profit=profit,
            business_id=outbound_order.id,
            created_by=getattr(payload, 'staff_id', None),
            category="手機銷售",
            payment_method=payload.payment_method,
            device_sn_code=device.sn_code,
            remark=f"設備出售出庫：{device.title} | 訂單號:{outbound_order.order_sn}",
        )
        db.add(financial_record)

        db.commit()

        # 6. 返回響應 (維持原始 API 契約)
        return SellDeviceResponse(
            id=device.id,
            model=device.title,
            order_sn=outbound_order.order_sn,
            sell_price=float(sell_price),
            profit=float(profit),
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
        InventoryModel.sn_code == clean_sn,
        InventoryModel.status == StockStatusEnum.IN_STOCK.value
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
        "created_at": inventory.created_at.isoformat()
    }

@router.get("/detail/{order_id}")
async def get_sales_detail(
    order_id: int, 
    x_shop_id: Optional[str] = Header(None, alias="X-Shop-Id"),
    db: AsyncSession = Depends(get_db_async)
):
    """獲取銷售單詳情"""
    # 1. 查詢主單據
    stmt = select(OutboundOrderModel).where(OutboundOrderModel.id == order_id)
    if x_shop_id:
        stmt = stmt.where(OutboundOrderModel.shop_id == int(x_shop_id))
    
    result = await db.execute(stmt)
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="找不到該銷售單據")

    # 2. 查詢客戶資訊
    partner_name, partner_phone = "散客", "-"
    if order.customer_id:
        p_stmt = select(Partner).where(Partner.id == order.customer_id)
        p_res = await db.execute(p_stmt)
        partner = p_res.scalars().first()
        if partner:
            partner_name = partner.name or partner_name
            partner_phone = partner.phone or partner_phone

    # 3. 關聯查詢 OutboundOrderItem 與 InventoryModel 獲取設備名稱與 IMEI/SN
    items_stmt = (
        select(
            OutboundOrderItem.selling_price,
            InventoryModel.title,
            InventoryModel.sn_code,
            InventoryModel.spec
        )
        .join(InventoryModel, OutboundOrderItem.inventory_id == InventoryModel.id)
        .where(OutboundOrderItem.outbound_order_id == order_id)
    )
    
    items_res = await db.execute(items_stmt)
    item_rows = items_res.all()

    devices = []
    for item in item_rows:
        # 拼接名稱與規格（如 "iPhone 15 Pro 256G"）
        model_name = item.title or "未命名設備"
        if item.spec:
            model_name = f"{model_name} {item.spec}"

        devices.append({
            "model_name": model_name,
            "imei": item.sn_code or "-",
            "price": float(item.selling_price or 0.0)
        })

    # 4. 組裝回傳數據
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "id": order.id,
            "order_sn": f"SO-{order.id}",
            "status": order.payment_status,  # 1: 完成, 2: 已退貨
            "partner_name": partner_name,
            "partner_phone": partner_phone,
            "total_amount": float(order.total_amount or getattr(order, "selling_price", 0.0) or 0.0),
            "created_at": order.created_at.isoformat(),
            "devices": devices
        }
    }

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

@router.post("/status")
async def update_inventory_status(
    req: UpdateStatusRequest,
    x_shop_id: Optional[str] = Header(None, alias="X-Shop-Id"),
    db: AsyncSession = Depends(get_db_async)
):
    """修改設備狀態 (如標記維修 status=3、標記報廢 status=4)"""
    
    stmt = select(InventoryModel).where(InventoryModel.id == req.id)
    if x_shop_id:
        stmt = stmt.where(InventoryModel.shop_id == int(x_shop_id))

    result = await db.execute(stmt)
    device = result.scalars().first()

    if not device:
        return {"code": 404, "msg": "設備不存在"}

    try:
        # 更新狀態 (直接給予 int/IntEnum 值)
        device.status = req.status.value
        device.updated_at = datetime.now()

        await db.commit()

        return {
            "code": 200,
            "msg": "狀態更新成功",
            "data": {
                "id": device.id,
                "status": device.status
            }
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")

@router.post("/refund", summary="辦理銷售退貨")
def refund_outbound_order(
    req: ReturnSalesRequest,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    shop_id = current_staff.shop_id

    try:
        # 1. 查詢原銷售單據與關聯庫存（加行鎖）
        order = (
            db.query(OutboundOrderModel)
            .filter(
                OutboundOrderModel.id == req.id,
                OutboundOrderModel.shop_id == shop_id
            )
            .with_for_update()
            .first()
        )

        if not order:
            raise HTTPException(status_code=404, detail="找不到該銷售單據")

        if order.payment_status == 0:  # 0: 已退款
            raise HTTPException(status_code=400, detail="該單據已辦理過退貨，請勿重複操作")

        items = db.query(OutboundOrderItem).filter(OutboundOrderItem.outbound_order_id == order.id).all()
        inventory_ids = [item.inventory_id for item in items]

        inventories = (
            db.query(InventoryModel)
            .filter(InventoryModel.id.in_(inventory_ids))
            .with_for_update()
            .all()
        )

        refund_amount = order.total_amount
        total_cost = Decimal("0.00")

        # 2. 處理設備：原設備變更為已退貨，並創建全新的待入庫紀錄
        for old_inv in inventories:
            total_cost += Decimal(str(old_inv.purchase_price or 0))
            
            # (1) 原設備標記為已退貨 (RETURNED = 7 或你的已退貨 Enum 值)
            old_inv.status = StockStatusEnum.RETURNED.value

            # (2) 重新複製建立一筆全新的設備紀錄，狀態為待入庫 (PENDING_IN = 1)
            new_inv = InventoryModel(
                shop_id=old_inv.shop_id,
                title=old_inv.title,
                sn_code=old_inv.sn_code,
                supplier_id=old_inv.supplier_id,
                purchase_price=old_inv.purchase_price,
                stock_quantity=1,
                status=StockStatusEnum.PENDING.value,  # 新記錄設為待入庫/待檢驗
                remark=f"來自銷售退貨 (原單號: {order.order_sn}, 原設備ID: {old_inv.id})"
            )
            db.add(new_inv)

        # 計算原單對應毛利
        refund_profit = refund_amount - total_cost

        # 3. 更新銷售單據狀態為 已退款 (0)
        order.payment_status = 0

        # 1. 查出原始銷售單或原始財務紀錄
        original_order = db.query(OutboundOrder).filter(OutboundOrder.id == order.id).first()

        # 4. 生成負數收入與毛利（紅字衝減）
        fin_sn = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_staff.id}"
        financial_record = FinancialRecord(
            shop_id=shop_id,
            type=1,                      # 1: 收入類別 (紅字衝減)
            record_sn=fin_sn,
            inventory_id=old_inv.id,
            amount=-refund_amount,       # 負數金額 -> 衝減銷售收入
            profit=-refund_profit,       # 負數毛利 -> 衝減銷售毛利
            category="sales_refund",
            business_id=order.id,
            created_by=current_staff.id,
            remark=f"銷售單退貨衝減: {order.order_sn}",
            record_time=original_order.created_at
        )
        db.add(financial_record)

        db.commit()
        return {
            "code": 200, 
            "message": "退貨成功，原設備已標記退貨，並已自動生成待入庫檢驗紀錄",
            "outbound_no": order.order_sn
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"退貨失敗: {str(e)}"
        )

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict

@router.get("/device/options", summary="獲取機型與屬性字典")
async def get_device_options(db: AsyncSession = Depends(get_db_async)):
    # 1. 預先查詢所有全域通用屬性 (model_id 為 None 或 0)
    global_stmt = (
        select(DeviceModelAttribute)
        .where(
            or_(
                DeviceModelAttribute.model_id.is_(None),
                DeviceModelAttribute.model_id == 0
            )
        )
        .order_by(DeviceModelAttribute.sort_order.asc())
    )
    global_result = await db.scalars(global_stmt)
    global_attrs = global_result.all()

    # 提取全域屬性列表
    global_colors = [a.attr_value for a in global_attrs if a.attr_type == 'color']
    global_storages = [a.attr_value for a in global_attrs if a.attr_type == 'storage']
    global_versions = [a.attr_value for a in global_attrs if a.attr_type == 'version']
    networks = [a.attr_value for a in global_attrs if a.attr_type == 'network']
    condition_details = [a.attr_value for a in global_attrs if a.attr_type == 'condition_detail']
    conditions = [a.attr_value for a in global_attrs if a.attr_type == 'condition']

    # 預設保底數據
    default_conditions = ['充新', '99新', '95新', '9新', '85新', '8新', '7新']
    default_networks = ['全網通 5G', '外版無鎖', '外版有鎖(卡貼)', '移動/聯通/電信單網', 'WiFi版']
    default_condition_details = ['全原無拆修', '換過電池', '換過螢幕', '小修/拆修過', '主板大修/擴容', '功能小瑕疵']

    # 2. 查詢所有已啟用的機型及其專屬屬屬性 (使用 selectinload 防止 N+1)
    models_stmt = (
        select(DeviceModel)
        .where(DeviceModel.is_active == True)
        .options(selectinload(DeviceModel.attributes))
        .order_by(DeviceModel.sort_order.asc())
    )
    models_result = await db.scalars(models_stmt)
    models = models_result.all()

    result = []
    for m in models:
        # 專屬屬性
        m_colors = [a.attr_value for a in m.attributes if a.attr_type == 'color']
        m_storages = [a.attr_value for a in m.attributes if a.attr_type == 'storage']
        m_versions = [a.attr_value for a in m.attributes if a.attr_type == 'version']

        # 優先用機型專屬，若無則降級使用全域通用屬性
        result.append({
            "id": m.id,
            "model_name": m.model_name,
            "colors": m_colors if m_colors else global_colors,
            "storages": m_storages if m_storages else global_storages,
            "versions": m_versions if m_versions else global_versions,
        })

    return {
        "code": 200,
        "data": {
            "models": result,
            "conditions": conditions if conditions else default_conditions,
            "networks": networks if networks else default_networks,
            "condition_details": condition_details if condition_details else default_condition_details
        }
    }