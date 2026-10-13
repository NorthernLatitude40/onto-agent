from fastapi import APIRouter, Depends, Query, Path, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

# 導入你的數據庫 Session 依賴與 SQLAlchemy Partner Model
from src.common.database import get_db, get_db_async
from src.model.partner_model import Partner  # 你的 Partner 數據模型
from src.model.partner_schema import PartnerCreate, PartnerResponse, ApiResponse
from src.common.exceptions import BusinessException

router = APIRouter()


@router.get(
    "/search",
    summary="根據電話號碼查詢往來單位",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "成功響應",
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "查詢成功",
                        "data": {
                            "id": 1,
                            "name": "客戶名稱",
                            "phone": "13800138000",
                            "type": 1,
                            "remark": "備註信息",
                            "receivable_amount": 100.50,
                            "payable_amount": 200.75
                        }
                    }
                }
            }
        },
        400: {
            "description": "請求參數錯誤",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "about:blank",
                        "title": "BAD_REQUEST",
                        "status": 400,
                        "detail": "手機號碼不能為空",
                        "instance": "/api/v1/partner/search"
                    }
                }
            }
        },
        404: {
            "description": "未找到資源",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "about:blank",
                        "title": "NOT_FOUND",
                        "status": 404,
                        "detail": "未找到相關客戶",
                        "instance": "/api/v1/partner/search"
                    }
                }
            }
        }
    }
)
async def search_partner_by_phone(
    phone: str = Query(..., min_length=1, max_length=20, description="手機號碼", examples=[{"value": "13800138000"}]),
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID", examples=[{"value": 1}]),
    db: AsyncSession = Depends(get_db_async)
):
    """
    前端輸入手機號後觸發，查詢資料庫中是否存在該歷史客戶/供應商
    
    遵循 RFC 9457 (RFC 7807 的擴展) 規範返回錯誤響應
    """
    phone = phone.strip()
    if not phone:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            detail="手機號碼不能為空",
            type_url="about:blank"
        )

    # 執行查詢
    stmt = select(Partner).where(Partner.phone == phone, Partner.shop_id == int(shop_id or 0))
    result = await db.execute(stmt)
    partner = result.scalars().first()

    if not partner:
        raise BusinessException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            detail="未找到相關客戶",
            type_url="about:blank"
        )

    # 轉為字典或 Pydantic 模型
    partner_data = PartnerResponse.model_validate(partner)

    return {
        "code": 200,
        "message": "查詢成功",
        "data": partner_data
    }


@router.post(
    "",
    summary="新增/保存往來單位",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "成功響應",
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "創建成功",
                        "data": {
                            "id": 1,
                            "name": "客戶名稱",
                            "phone": "13800138000",
                            "type": 1,
                            "remark": "備註信息",
                            "receivable_amount": 100.50,
                            "payable_amount": 200.75
                        }
                    }
                }
            }
        },
        400: {
            "description": "請求參數錯誤",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "about:blank",
                        "title": "BAD_REQUEST",
                        "status": 400,
                        "detail": "客戶名稱不能為空",
                        "instance": "/api/v1/partner"
                    }
                }
            }
        },
        500: {
            "description": "內部伺服器錯誤",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "about:blank",
                        "title": "INTERNAL_SERVER_ERROR",
                        "status": 500,
                        "detail": "創建客戶時發生未知錯誤",
                        "instance": "/api/v1/partner"
                    }
                }
            }
        }
    }
)
async def create_partner(
    partner_in: PartnerCreate,
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID", examples=[{"value": 1}]),
    db: AsyncSession = Depends(get_db)
):
    """
    提交單據時，若為新客戶/供應商，可呼叫此接口建立記錄
    
    遵循 RFC 9457 (RFC 7807 的擴展) 規範返回錯誤響應
    """
    # 檢查必填字段
    if not partner_in.name:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            detail="客戶名稱不能為空",
            type_url="about:blank"
        )

    # 檢查電話是否已存在
    if partner_in.phone:
        stmt = select(Partner).where(Partner.phone == partner_in.phone, Partner.shop_id == int(shop_id or 0))
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
            return {
                "code": 200,
                "message": "客戶已存在，已更新信息",
                "data": PartnerResponse.model_validate(existing_partner)
            }

    # 創建新單位
    new_partner = Partner(
        name=partner_in.name,
        phone=partner_in.phone,
        type=partner_in.type,
        remark=partner_in.remark,
        receivable_amount=0.00,
        payable_amount=0.00,
        shop_id=shop_id or 0
    )
    
    try:
        db.add(new_partner)
        await db.commit()
        await db.refresh(new_partner)

        return {
            "code": 200,
            "message": "創建成功",
            "data": PartnerResponse.model_validate(new_partner)
        }
    except Exception as e:
        await db.rollback()
        raise BusinessException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            detail=f"創建客戶時發生未知錯誤: {str(e)}",
            type_url="about:blank"
        )


@router.get(
    "/{partner_id}",
    summary="獲取往來單位詳情",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "成功響應",
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "查詢成功",
                        "data": {
                            "id": 1,
                            "name": "客戶名稱",
                            "phone": "13800138000",
                            "type": 1,
                            "remark": "備註信息",
                            "receivable_amount": 100.50,
                            "payable_amount": 200.75
                        }
                    }
                }
            }
        },
        400: {
            "description": "請求參數錯誤",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "about:blank",
                        "title": "BAD_REQUEST",
                        "status": 400,
                        "detail": "partner_id 必須是正整數",
                        "instance": "/api/v1/partner/{partner_id}"
                    }
                }
            }
        },
        404: {
            "description": "未找到資源",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "about:blank",
                        "title": "NOT_FOUND",
                        "status": 404,
                        "detail": "該往來單位不存在",
                        "instance": "/api/v1/partner/{partner_id}"
                    }
                }
            }
        }
    }
)
async def get_partner_detail(
    partner_id: int = Path(..., gt=0, description="往來單位ID", examples=[1]),
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID", examples=[1]),
    db: AsyncSession = Depends(get_db)
):
    """
    獲取往來單位詳情
    
    遵循 RFC 9457 (RFC 7807 的擴展) 規範返回錯誤響應
    """
    stmt = select(Partner).where(Partner.id == partner_id, Partner.shop_id == int(shop_id or 0))
    result = await db.execute(stmt)
    partner = result.scalars().first()

    if not partner:
        raise BusinessException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            detail="該往來單位不存在",
            type_url="about:blank"
        )

    return {
        "code": 200,
        "message": "查詢成功",
        "data": PartnerResponse.model_validate(partner)
    }