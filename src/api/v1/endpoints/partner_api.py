from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

# 導入你的數據庫 Session 依賴與 SQLAlchemy Partner Model
from src.common.database import get_db, get_db_async
from src.model.partner_model import Partner  # 你的 Partner 數據模型
from src.model.partner_schema import PartnerCreate, PartnerResponse
from src.common.exceptions import not_found, conflict, bad_request
from src.model.response_models import ApiResponse, CreatedResponse, success_response

router = APIRouter()


@router.get("/search", summary="根據電話號碼查詢往來單位")
async def search_partner_by_phone(
    phone: str = Query(..., description="手機號碼"),
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: AsyncSession = Depends(get_db_async)
):
    """
    前端輸入手機號後觸發，查詢資料庫中是否存在該歷史客戶/供應商
    """
    phone = phone.strip()
    if not phone:
        return None

    # 執行查詢
    stmt = select(Partner).where(Partner.phone == phone, Partner.shop_id == int(shop_id))
    result = await db.execute(stmt)
    partner = result.scalars().first()

    if not partner:
        return None

    # 轉為字典或 Pydantic 模型
    partner_data = PartnerResponse.model_validate(partner)

    if not partner:
        return None

    # 轉為字典或 Pydantic 模型
    partner_data = PartnerResponse.model_validate(partner)

    return success_response(data=partner_data, message="查詢成功")


@router.post("", summary="新增/保存往來單位", response_model=PartnerResponse)
async def create_partner(
    partner_in: PartnerCreate,
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    提交單據時，若為新客戶/供應商，可呼叫此接口建立記錄
    """
    # 檢查電話是否已存在
    if partner_in.phone:
        stmt = select(Partner).where(Partner.phone == partner_in.phone, Partner.shop_id == int(shop_id))
        result = await db.execute(stmt)
        existing_partner = result.scalars().first()

        if existing_partner:
            # 如果已存在，更新名稱（若有變化）並返回
            existing_partner.name = partner_in.name
            if partner_in.type != existing_partner.type and existing_partner.type != 3:
                # 若原本是客戶(1)現在又是供應商(2)，更新為二者皆是(3)
                existing_partner.type = 3
            await db.commit()
            await db.refresh(existing_partner)
            return CreatedResponse(data=PartnerResponse.model_validate(existing_partner), message="往來單位已存在，資料已更新")

    # 創建新單位
    new_partner = Partner(
        name=partner_in.name,
        phone=partner_in.phone,
        type=partner_in.type,
        remark=partner_in.remark,
        receivable_amount=0.00,
        payable_amount=0.00,
        shop_id=shop_id
    )
    
    db.add(new_partner)
    await db.commit()
    await db.refresh(new_partner)

    return CreatedResponse(data=PartnerResponse.model_validate(new_partner), message="往來單位創建成功")


@router.get("/{partner_id}", response_model=ApiResponse, summary="獲取往來單位詳情")
async def get_partner_detail(
    partner_id: int,
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Partner).where(Partner.id == partner_id, Partner.shop_id == int(shop_id))
    result = await db.execute(stmt)
    partner = result.scalars().first()

    if not partner:
        raise not_found("該往來單位不存在")

    return success_response(data=PartnerResponse.model_validate(partner), message="查詢成功")

