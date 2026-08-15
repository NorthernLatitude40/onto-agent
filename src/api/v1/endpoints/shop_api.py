from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy import func

from src.common.database import get_db
from src.model.staff_model import StaffModel
from src.model.clark_schema import StaffUpdateSchema, StaffResponse
from src.model.user_model import UserModel
from src.config.config import settings
from src.common.dict import  ShopRole
from src.api.auth_api import get_current_user, create_access_token
from src.api.auth_api import get_current_user 
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload, ShopSimpleResponse
from src.model.shop_model import ShopModel
from src.common.logger import get_logger
from src.common.exceptions import BusinessException
from src.common.i18n import ErrorCode, get_i18n_message

logger = get_logger("API_SERVICE")

router = APIRouter()

# ──────── 商家自主开店/创建店铺 API (单表架构重构版) ────────
@router.post("/create", response_model=ShopResponse, status_code=status.HTTP_201_CREATED, summary="创建店铺")
def create_shop(
    payload: CreateShopPayload,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)  # 🌟 修正：创店的主体是登录账号 User
):
    """
    商家自主开店逻辑 (单表架构)：
    1. 在 shops 表插入新店铺记录
    2. 在 staff 表中直接为当前 User 创建一条店主 (OWNER) 档案，并绑定 shop_id
    """
    # 确定 owner_id（使用当前登录用户的微信账号 ID）
    owner_id = current_user.id

    try:
        # ---------------------------------------------------------
        # 1. 创建店铺主表记录
        # ---------------------------------------------------------
        new_shop = ShopModel(
            name=payload.name,
            logo=payload.logo,
            contact_name=payload.contact_name or getattr(current_user, "nickname", "店长"),
            contact_phone=payload.contact_phone,
            province=payload.province,
            city=payload.city,
            district=payload.district,
            address_detail=payload.address_detail,
            is_active=True
        )
        db.add(new_shop)
        db.flush()  # 刷入数据库以获取自动生成的 new_shop.id

        # ---------------------------------------------------------
        # 2. 在 StaffModel 单表中直接生成店主 (OWNER) 档案
        # ---------------------------------------------------------
        owner_staff_profile = StaffModel(
            shop_id=new_shop.id,
            user_id=owner_id,                                       # 绑定当前用户的 user_id
            name=payload.contact_name or getattr(current_user, "nickname", "店长"),
            phone=payload.contact_phone or getattr(current_user, "phone", None),
            avatar=payload.logo or getattr(current_user, "avatar", None),
            role=ShopRole.OWNER.value,                              # 角色设置为 OWNER
            status=1                                                # 1: 直接激活/在职状态
        )
        db.add(owner_staff_profile)

        # ---------------------------------------------------------
        # 3. 事务提交并刷新
        # ---------------------------------------------------------
        db.commit()
        db.refresh(new_shop)

        return new_shop

    except Exception as e:
        db.rollback()
        logger.error(f"创建店铺失败，原始异常: {str(e)}", exc_info=True)
        raise BusinessException(
            detail="创建店铺失败", 
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
# ==================== 5. 刪：刪除店鋪 (軟刪除) ====================
@router.delete("/{target_shop_id}", summary="刪除店鋪(僅Owner可操作)")
def delete_shop(
    target_shop_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
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

# ──────── 修改店铺信息 API (单表架构重构版) ────────
@router.put("/update", summary="修改店铺信息")
def update_shop_info(
    payload: UpdateShopPayload,
    db: Session = Depends(get_db),
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    current_user: UserModel = Depends(get_current_user)  # 🌟 修正：当前登录账号 User
):
    """
    修改店铺信息接口：
    - 校验当前登录用户在 X-Shop-Id 店铺中是否有在职档案
    - 仅允许店长/店主/管理员 (owner/manager/admin) 修改店铺基础信息
    """
    # ---------------------------------------------------------
    # 0. 请求头强校验
    # ---------------------------------------------------------
    if not x_shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求头缺少 X-Shop-Id 参数！"
        )

    # ---------------------------------------------------------
    # 1. 鉴权与权限检查：从 StaffModel 查询当前用户在该店的档案
    # ---------------------------------------------------------
    current_staff = db.query(StaffModel).filter(
        StaffModel.shop_id == x_shop_id,
        StaffModel.user_id == current_user.id,
        StaffModel.status == 1  # 必须是正式激活/在职状态
    ).first()

    if not current_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权管理该店铺或在该店铺的身份已失效！"
        )

    # 角色校验：只有店主/店长/管理员有权修改店铺信息
    allowed_roles = {ShopRole.OWNER.value, "owner", "manager", "admin"}
    if current_staff.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：普通员工无权修改店铺信息！"
        )

    # ---------------------------------------------------------
    # 2. 查询目标店铺记录
    # ---------------------------------------------------------
    shop = db.query(ShopModel).filter(ShopModel.id == x_shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应店铺，无法修改！"
        )

    # ---------------------------------------------------------
    # 3. 动态更新非空字段
    # ---------------------------------------------------------
    update_data = payload.model_dump(exclude_unset=True, exclude={"shop_id", "id"}) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True, exclude={"shop_id", "id"})
    
    for key, value in update_data.items():
        if value is not None and hasattr(shop, key):
            setattr(shop, key, value)

    # ---------------------------------------------------------
    # 4. 提交事务并回传数据
    # ---------------------------------------------------------
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
                "province": shop.province,
                "city": shop.city,
                "district": shop.district,
                "address_detail": shop.address_detail,
                "address": f"{shop.province or ''}{shop.city or ''}{shop.district or ''}{shop.address_detail or ''}"
            }
        }
    except Exception as e:
        db.rollback()
        logger.exception("【API 错误】修改店铺信息失败:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新店铺信息失败: {str(e)}"
        )

# ──────── 🌟 获取当前店铺信息 API (单表架构重构版) ────────
@router.get(
    "/current",
    response_model=Optional[ShopResponse],  # 允许返回店铺对象或 None (JSON null)
    status_code=status.HTTP_200_OK,
    summary="获取当前登录用户关联的店铺信息"
)
def get_current_shop_info(
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)  # 🌟 依赖微信账号 User
):
    """
    提供给小程序【设置页/店铺信息】使用：
    查询当前选择/关联的真实店铺数据及员工总数。
    - 优先根据 Header 里的 X-Shop-Id 查找。
    - 若 Header 未传，自动查找该 User 关联的第一个在职店铺。
    - 若用户无任何店铺关联，返回 null。
    """
    target_shop_id = x_shop_id

    # ---------------------------------------------------------
    # 1. 确定目标 shop_id
    # ---------------------------------------------------------
    if target_shop_id:
        # Header 指定了店铺，校验当前用户在该店铺是否拥有在职档案
        current_staff = db.query(StaffModel).filter(
            StaffModel.shop_id == target_shop_id,
            StaffModel.user_id == current_user.id,
            StaffModel.status == 1  # 必须是在职激活状态
        ).first()

        if not current_staff:
            raise BusinessException(
                code=ErrorCode.NOT_SHOP_STAFF, 
                detail="您不是该店铺的在职员工或无权访问此店铺！", 
                status_code=status.HTTP_403_FORBIDDEN
            )
    else:
        # Header 未传，自动查询当前用户关联的第一个在职店铺档案
        latest_staff_profile = db.query(StaffModel).filter(
            StaffModel.user_id == current_user.id,
            StaffModel.status == 1
        ).order_by(StaffModel.id.desc()).first()

        if not latest_staff_profile:
            # 说明该账号尚未关联或创建任何店铺，优雅返回 None
            return None

        target_shop_id = latest_staff_profile.shop_id

    # ---------------------------------------------------------
    # 2. 查询店铺主数据
    # ---------------------------------------------------------
    shop = db.query(ShopModel).filter(
        ShopModel.id == target_shop_id, 
        ShopModel.is_active == True
    ).first()

    if not shop:
        raise BusinessException(detail="目标店铺不存在或已被禁用", status_code=status.HTTP_404_NOT_FOUND)

    # ---------------------------------------------------------
    # 3. 统计该店铺下在职员工总数 (单表 StaffModel 统计)
    # ---------------------------------------------------------
    staff_count = db.query(func.count(StaffModel.id)).filter(
        StaffModel.shop_id == target_shop_id,
        StaffModel.status == 1  # 1: 已绑定在职
    ).scalar() or 1

    # 动态将统计出来的员工总数挂载到 shop 对象上（配合 ShopResponse 渲染）
    shop.staff_count = staff_count

    return shop

@router.get(
    "/my-shops", 
    summary="获取当前用户关联的店铺列表(含角色、Staff ID及默认店铺标识)"
)
def get_my_shops(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # 1. 获取当前用户的默认店铺 ID 和默认员工 ID
    user_default_shop_id = getattr(current_user, "default_shop_id", None)
    user_default_staff_id = getattr(current_user, "default_staff_id", None)

    # 2. 查询当前用户在职且生效的店铺及员工身份列表
    results = (
        db.query(ShopModel, StaffModel.role, StaffModel.id.label("staff_id"))
        .join(StaffModel, ShopModel.id == StaffModel.shop_id)
        .filter(
            StaffModel.user_id == current_user.id,
            StaffModel.status == 1,
            ShopModel.is_active == True
        )
        .all()
    )

    shops_list = []
    for shop, role, staff_id in results:
        # 🌟 优先通过 staff_id 精确匹配默认身份；若无 default_staff_id 则退化匹配 shop_id
        if user_default_staff_id is not None:
            is_default = (staff_id == user_default_staff_id)
        elif user_default_shop_id is not None:
            is_default = (shop.id == user_default_shop_id)
        else:
            is_default = False

        shops_list.append({
            "id": shop.id,
            "staff_id": staff_id,  # 对应的 staff_id
            "name": shop.name,
            "logo": shop.logo,
            "contact_name": shop.contact_name,
            "contact_phone": shop.contact_phone,
            "role": role,  # 当前账号在该身份下的角色
            "is_default": is_default,  # 🌟 标识是否为默认身份
            "address": f"{shop.province or ''}{shop.city or ''}{shop.district or ''}{shop.address_detail or ''}"
        })

    # 3. 如果用户尚未设置默认店铺/身份（或原默认记录已失效），默认将列表中第 0 个设为 is_default
    if shops_list and not any(s["is_default"] for s in shops_list):
        shops_list[0]["is_default"] = True

    return shops_list