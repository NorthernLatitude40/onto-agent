from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from datetime import datetime

from src.common.database import get_db
from src.model.inventory_model import InventoryModel  # 庫存/設備表
from src.model.partner_model import Partner as  PartnerModel     # 供應商/合作夥伴表
from src.model.staff_model import StaffModel          # 員工表
from src.api.auth_api import get_current_staff   # 直連 staff 的驗證依賴
from src.model.order_model import OutboundOrderModel
from src.model.purchase_schema import DeviceItem, PurchaseDetailResponse, ConfirmInboundRequest
from src.common.dict import InboundStatusEnum


router = APIRouter()


@router.get("/list", summary="獲取進銷存單據列表 (進貨/銷售二合一)")
def get_order_list(
    order_type: Optional[int] = Query(None, description="單據類型: 1-進貨/入庫, 2-銷售/出庫 (不傳則查詢全部)"),
    status: Optional[InboundStatusEnum] = Query(
        None, 
        description="1-未完成入庫, 2-已完成入庫, 3-已取消, 0-已退貨"
    ),
    keyword: Optional[str] = Query(None, description="關鍵字: 單號/IMEI/合作方名稱/電話"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(20, ge=1, le=100, description="每頁筆數"),
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    """
    統一查詢門店下的進貨與銷售單據
    """
    shop_id = current_staff.shop_id
    all_orders = []

    kw = f"%{keyword.strip()}%" if (keyword and keyword.strip() and keyword.strip().lower() not in ["undefined", "null"]) else None

    # 1. 查詢採購/入庫單據 (order_type == 1 或未指定)
    if order_type is None or order_type == 1:
        p_query = (
            db.query(InventoryModel, PartnerModel)
            .outerjoin(PartnerModel, InventoryModel.supplier_id == PartnerModel.id)
            .filter(InventoryModel.shop_id == shop_id,
                    InventoryModel.status == status.value
                    )
        )
        if kw:
            p_query = p_query.filter(
                or_(
                    InventoryModel.sn_code.ilike(kw),
                    InventoryModel.title.ilike(kw),
                    PartnerModel.name.ilike(kw),
                    PartnerModel.phone.ilike(kw)
                )
            )
        for inv, supplier in p_query.all():
            all_orders.append({
                "id": inv.id,
                "title": inv.title,
                "order_sn": f"IN-{inv.id}",
                "order_type": 1,  # 1: 進貨
                "category": inv.category,
                "type_name": "進貨入庫",
                "partner_name": supplier.name if supplier else "未知供應商",
                "partner_phone": supplier.phone if supplier else "-",
                "total_amount": float(inv.purchase_price or 0.0),
                "total_profit": 0.0,
                "status": inv.status,
                "created_at": inv.created_at
            })

    # 2. 查詢銷售/出庫單據 (order_type == 2 或未指定)
    if order_type is None or order_type == 2:
        s_query = (
            db.query(OutboundOrderModel, PartnerModel)
            .outerjoin(PartnerModel, OutboundOrderModel.customer_id == PartnerModel.id)
            .filter(OutboundOrderModel.shop_id == shop_id)
        )
        # 2. 如果 status 有傳值（非 None），才加上狀態過濾條件
        if status is not None:
            # 若 status 是 Enum 類型，可以使用 status.value 或直接傳入
            status_val = status.value if hasattr(status, 'value') else status
            s_query = s_query.filter(OutboundOrderModel.payment_status == status_val)

        if kw:
            s_query = s_query.filter(
                or_(
                    OutboundOrderModel.order_sn.ilike(kw),
                    PartnerModel.name.ilike(kw),
                    PartnerModel.phone.ilike(kw)
                )
            )
        for order, customer in s_query.all():
            all_orders.append({
                "id": order.id,
                "order_sn": order.order_sn,
                "order_type": 2,  # 2: 銷售
                "category": inv.category,
                "type_name": "銷售出庫",
                "partner_name": customer.name if customer else "散客/零售客戶",
                "partner_phone": customer.phone if customer else "-",
                "total_amount": float(order.total_amount or 0.0),
                "total_profit": float(order.total_profit or 0.0),
                "status": order.payment_status,
                "created_at": order.created_at
            })

    # 3. 按時間倒序排序 (最新單據排在最前面)
    all_orders.sort(key=lambda x: x["created_at"] if x["created_at"] else "", reverse=True)

    # 4. 記憶體中做分頁處理
    total = len(all_orders)
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = all_orders[start:end]

    # 5. 格式化時間字串
    for item in paged_items:
        if item["created_at"] and not isinstance(item["created_at"], str):
            item["created_at"] = item["created_at"].strftime("%Y-%m-%d %H:%M")

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": paged_items
    }

@router.get("/detail/{inv_id}")
def get_purchase_detail(inv_id: int, db: Session = Depends(get_db)):
    """
    1. 獲取進貨單據詳情
    """
    # 1. 查詢庫存主記錄
    inv = db.query(InventoryModel).filter(InventoryModel.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="找不到該進貨單據")

    # 2. 查詢關聯的供應商資訊
    partner_name = "未知供應商"
    partner_phone = "-"
    if inv.supplier_id:
        supplier = db.query(PartnerModel).filter(PartnerModel.id == inv.supplier_id).first()
        if supplier:
            partner_name = supplier.name or partner_name
            partner_phone = supplier.phone or partner_phone

    # 3. 組合串號/設備清單 (假設 imei 存在 inv.imei 或關聯表)
    device_list = []
    if inv.sn_code:
        device_list.append({"imei": inv.sn_code})

    items = [
        {
            "model_name": inv.title or inv.model_name or "未知機型",
            "devices": device_list
        }
    ]

    # 4. 構建回傳格式
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "id": inv.id,
            "order_sn": f"IN-{inv.id}",
            "category": inv.category or 1,
            "status": inv.status,  # 1: 待確認, 2: 已入庫
            "partner_name": partner_name,
            "partner_phone": partner_phone,
            "total_amount": float(inv.purchase_price or 0.0),
            "created_at": inv.created_at.strftime("%Y-%m-%d %H:%M:%S") if inv.created_at else "",
            "items": items
        }
    }


@router.post("/confirm-inbound")
def confirm_inbound(req: ConfirmInboundRequest, db: Session = Depends(get_db)):
    """
    2. 確認入庫接口（將待確認 status=1 改為已入庫 status=2）
    """
    inv = db.query(InventoryModel).filter(InventoryModel.id == req.id).first()
    if not inv:
        return {"code": 404, "msg": "單據不存在"}

    if inv.status == 2:
        return {"code": 400, "msg": "該單據已完成入庫，請勿重複操作"}

    try:
        # 更新狀態為已入庫 (2)
        inv.status = 2
        inv.updated_at = datetime.now()
        
        # 若有相關庫存數量變更邏輯，在此處寫入
        # db.add(inventory_stock) ...

        db.commit()
        return {
            "code": 200,
            "msg": "確認入庫成功",
            "data": {"id": inv.id, "status": inv.status}
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"入庫失敗: {str(e)}"
        )