from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy import func

from src.common.database import get_db
from src.model.staff_model import StaffModel
from src.model.clark_schema import StaffUpdateSchema, StaffResponse
from src.dependencies.permissions import allow_admin, allow_shop_manager, allow_shop_staff
from src.model.user_model import User
from src.config.config import settings
from src.common.dict import SystemRole, ShopRole
from src.api.auth_api import get_current_user, create_access_token
from src.api.auth_api import get_current_user 
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload, ShopSimpleResponse
from src.model.shop_model import ShopModel
from src.common.logger import get_logger
from src.common.exceptions import BusinessException
from src.model.shop_staff_model import ShopStaffModel
from src.common.i18n import ErrorCode, get_i18n_message

logger = get_logger("API_SERVICE")

router = APIRouter()

# ──────── 商家自主开店/创建店铺 API ────────
@router.post("/create", response_model=ShopResponse, status_code=status.HTTP_201_CREATED, summary="创建店铺")
def create_shop(
    payload: CreateShopPayload,
    db: Session = Depends(get_db),
    current_user: StaffModel = Depends(get_current_user)
):
    """
    方案 B - 商家自主开店逻辑：
    1. 在 shops 表插入新店铺记录
    2. 将当前登录用户绑定到该店铺 (user.shop_id = new_shop.id)
    3. 自动将该用户角色升级为店铺管理员/店长 (UserRole.ADMIN)
    """
    # 1. 确定 owner_id：如果未传，默认为当前登录用户
    owner_id = payload.owner_id or current_user.id

    try:
        # 2. 落库创建店铺
        new_shop = ShopModel(
            name=payload.name,
            logo=payload.logo,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            province=payload.province,
            city=payload.city,
            district=payload.district,
            address_detail=payload.address_detail,
            owner_id=current_user.id,
            is_active=True
        )
        db.add(new_shop)
        db.flush()  # 获取自动生成的 new_shop.id

        # 3. 绑定用户并升级为该店铺的创建者/店长
        staff_relation = ShopStaffModel(
            role=ShopRole.OWNER.value,      # 記得用 .value 轉成純字串 (或 ShopRole.OWNER)
            shop_id=new_shop.id,
            staff_id=current_user.id, 
            status=1
        )
        db.add(staff_relation)

        db.commit()
        db.refresh(new_shop)

        return new_shop

    except Exception as e:
        db.rollback()
        logger.error(f"創建店鋪失敗，原始異常: {str(e)}", exc_info=True)
        raise BusinessException(detail="创建店铺失败", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== 5. 刪：刪除店鋪 (軟刪除) ====================
@router.delete("/{target_shop_id}", summary="刪除店鋪(僅Owner可操作)")
def delete_shop(
    target_shop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 驗證操作者是否為該店鋪的 Owner
    staff = db.query(StaffModel).filter(
        StaffModel.user_id == current_user.id,
        StaffModel.shop_id == target_shop_id,
        StaffModel.role == "owner"
    ).first()

    if not staff:
        raise HTTPException(status_code=403, detail="權限不足：只有店主可以註銷店鋪")

    shop = db.query(ShopModel).filter(ShopModel.id == target_shop_id).first()
    if shop:
        shop.status = 0  # 軟刪除
        db.commit()

    return {"message": "店鋪已成功解散/註銷"}

# ──────── 修改店铺信息 API ────────
@router.put("/update", summary="修改店铺信息")
def update_shop_info(
    payload: UpdateShopPayload,
    db: Session = Depends(get_db),
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    current_user: StaffModel = Depends(get_current_user)
):
    """
    修改店铺信息接口：
    - 仅允许店长/管理员 (UserRole.ADMIN 或 role == 'admin') 修改
    - 普通员工越权修改将直接被拒绝
    """
    staff_relation = db.query(ShopStaffModel).filter(
        ShopStaffModel.shop_id == x_shop_id,
        ShopStaffModel.staff_id == current_user.id
    ).first()

    # 确定目标店铺 ID（默认修改用户当前绑定的店铺）
    target_shop_id = x_shop_id

    # 跨店修改鉴权：防止修改其他店铺
    if target_shop_id != getattr(staff_relation, "shop_id", 1):
         raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="您无权修改其他店铺的信息！"
                    )
           

    shop = db.query(ShopModel).filter(ShopModel.id == target_shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应店铺，无法修改！"
        )

    # 动态更新非空字段
    update_data = payload.model_dump(exclude_unset=True, exclude={"shop_id"})
    for key, value in update_data.items():
        if value is not None:
            setattr(shop, key, value)

    try:
        db.commit()
        db.refresh(shop)
        return {
            "code": 200,
            "message": "店铺信息更新成功！",
            "data": {
                "id": shop.id,
                "name": shop.name,
                "logo": shop.logo,
                "contact_name": shop.contact_name,
                "contact_phone": shop.contact_phone,
                "address": f"{shop.province or ''}{shop.city or ''}{shop.district or ''}{shop.address_detail or ''}"
            }
        }
    except Exception as e:
        db.rollback()
        logger.exception("【API 错误】修改店铺信息失败:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )

# ──────── 🌟 新增接口 1：获取当前店铺信息 ────────
@router.get(
    "/current",
    response_model=Optional[ShopResponse],  # 允许返回店铺对象或 None (JSON null)
    status_code=status.HTTP_200_OK,
    summary="获取当前登录用户关联的店铺信息"
)
def get_current_shop_info(
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: Session = Depends(get_db),
    current_user: StaffModel = Depends(get_current_user)
):
    """
    提供给小程序【设置页/店铺信息】使用：
    查询当前选择/关联的真实店铺数据及员工总数。
    """
    # 1. 确定当前要查询的 shop_id：优先取 Header 传参，次之从关联关系获取
    target_shop_id = x_shop_id

    if not target_shop_id:
        #如果用户未指定，则去查默认店铺
        if current_user.shop_id:
            staff_ralations = db.query(ShopStaffModel).filter(
                ShopStaffModel.staff_id == current_user.id,  # 👈 只要留下這行即可！
                ShopStaffModel.shop_id == current_user.shop_id
            ).first()
            
            if not staff_ralations:
                raise BusinessException(code=ErrorCode.NOT_SHOP_STAFF, status_code=400)
            # 没问题的话当前默认店铺获取成功
            target_shop_id = current_user.shop_id

    # 3. 查询店铺主数据
    shop = db.query(ShopModel).filter(ShopModel.id == target_shop_id, ShopModel.is_active == True).first()
    if not shop:
        raise BusinessException(detail="店铺不存在", status_code=400)

    # 4. 统计该店铺下激活的员工总数 (从 ShopStaff 表统计)
    staff_count = db.query(func.count(ShopStaffModel.staff_id)).filter(
        ShopStaffModel.shop_id == target_shop_id,
        ShopStaffModel.status == 1
    ).scalar() or 1
    shop.staff_count = staff_count

    return shop

# ==================== 2. 查：獲取當前用戶的所有店鋪列表 ====================
@router.get(
    "/my-shops", 
    response_model=List[ShopSimpleResponse],  # 建議指定回傳的 Schema，符合 Bare Payload
    summary="獲取當前用戶關聯的店鋪列表"
)
def get_my_shops(
    db: Session = Depends(get_db),
    current_user: StaffModel = Depends(get_current_user)
):
    """
    獲取當前登入用戶所有在職（status=1）且店鋪未被刪除（status!=0）的店鋪列表
    """
    # 🌟 關鍵修復：跨三表 (User -> Staff -> ShopStaff -> Shop) 進行關聯查詢
    shops = (
        db.query(ShopModel)
        .join(ShopStaffModel, ShopModel.id == ShopStaffModel.shop_id)
        .join(StaffModel, ShopStaffModel.staff_id == StaffModel.id)
        .filter(
            StaffModel.id == current_user.id,     # 1. 匹配當前登入用戶
            ShopStaffModel.status == 1,                # 2. 必須是在該店正常在職的員工 (1: 在職)
            ShopModel.is_active == True                     # 3. 排除已軟刪除/停用的店鋪
        )
        .all()
    )

    # 🌟 如果用戶未關聯任何店鋪，回傳空陣列 [] (Bare Payload 規範)
    return shops