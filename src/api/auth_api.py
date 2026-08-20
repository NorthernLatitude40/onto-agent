from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

# 根据你的实际项目路径导入
from src.common.database import get_db
from src.config.config import settings
from src.model.schema import UserUpdateSchema
from src.model.user_model import UserModel
from src.model.schema import UserOutSchema, TokenOutSchema, UserUpdateSchema
from src.model.response_models import LoginResponse, UserResponse
from src.common.exceptions import BusinessException
from src.model.staff_model import StaffModel
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from src.common.i18n import ErrorCode, get_i18n_message
from src.model.staff_model import StaffModel
from src.common.logger import get_logger
from src.common.dict import ShopRole

logger = get_logger("API_SERVICE")

router = APIRouter(prefix="/api/v1/auth", tags=["认证鉴权"])

security = HTTPBearer()


# ----------------------------------------------------------------------
# Helper Functions & Dependencies
# ----------------------------------------------------------------------

def create_access_token(data: dict) -> str:
    """生成带 UTC 时间戳的 JWT Token"""
    to_encode = data.copy()
    # 强制使用 UTC 时间，避免不同服务器时区不一致导致的 Token 提前失效问题
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ──────── 🌟 1. 基础依赖：解析 Token 获取当前登录账号 (User) ────────
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserModel:
    """
    全局账号鉴权依赖：
    只校验 JWT Token 合法性，不强绑定 X-Shop-Id。
    适用于：获取个人信息、创建店铺、查询用户店铺列表等通用接口。
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证已过期或无效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


# ──────── 🌟 2. 店铺上下文依赖：获取当前用户在指定店铺的员工档案 (StaffModel) ────────
def get_current_staff(
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StaffModel:
    """
    店铺履职鉴权依赖：
    根据 Header 中的 X-Shop-Id + 当前登录用户 ID，直接在 StaffModel 单表中精确定位员工档案。
    适用于：更新员工信息、修改店铺、管理商品等店铺内部业务接口。
    """
    if not x_shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求头缺少 X-Shop-Id 参数，请选择店铺后再操作"
        )

    # 单表精准定位：匹配 shop_id + user_id
    staff = db.query(StaffModel).filter(
        StaffModel.shop_id == x_shop_id,
        StaffModel.user_id == current_user.id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该店铺的员工或无权访问此店铺"
        )

    # 🌟 状态校验：0-待绑定, 1-正常在职, 2-已禁用/离职
    if staff.status == 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="您在该店铺的账号已被禁用，请联系管理员",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if staff.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的员工身份尚未激活，请先完成邀请绑定"
        )

    return staff


# ──────── 🌟 3. 权限管理依赖：验证当前员工是否为店长/管理员 ────────
def allow_shop_manager(
    current_staff: StaffModel = Depends(get_current_staff)
) -> StaffModel:
    """店长/管理员管理权限校验依赖"""
    allowed_roles = {ShopRole.OWNER.value, "owner", "manager", "admin"}
    if current_staff.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：仅限店长或系统管理员操作"
        )
    return current_staff


class PermissionChecker:
    """RBAC 权限检查器"""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="暂无访问权限"
            )
        return current_user


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

class WxLoginPayload(BaseModel):
    code: str


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

# ──────── 微信小程序登录/注册 API (单表架构重构版) ────────
@router.post(
    "/wx-login", 
    response_model=LoginResponse, 
    status_code=status.HTTP_200_OK,
    summary="微信小程序登录/注册"
)
async def wx_login(payload: WxLoginPayload, db: Session = Depends(get_db)):
    """
    微信登录/注册接口：
    1. 拿 code 换取 openid
    2. 若用户不存在，创建 User 并初始化默认体验店铺的 Staff 档案
    3. 移除 ShopStaffModel 中间表，所有职务与店铺绑定关系直接落入 StaffModel
    4. 签发 JWT Token 并返回前端所需的用户信息
    """
    # ---------------------------------------------------------
    # 1. 校验 Code
    # ---------------------------------------------------------
    if not payload.code or not payload.code.strip():
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.WX_CODE_EMPTY
        )

    # ---------------------------------------------------------
    # 2. 请求微信接口换取 session_key 和 openid
    # ---------------------------------------------------------
    wx_url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WX_APP_ID,
        "secret": settings.WX_APP_SECRET,
        "js_code": payload.code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(wx_url, params=params)
            resp.raise_for_status()
            wx_data = resp.json()
        except httpx.RequestError:
            raise BusinessException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="WX_SERVICE_UNAVAILABLE"
            )
        
    # ---------------------------------------------------------
    # 3. 检查微信 API 返回状态
    # ---------------------------------------------------------
    if wx_data.get("errcode", 0) != 0:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.WX_LOGIN_FAILED,
            extra={"wx_errmsg": wx_data.get("errmsg")} 
        )

    openid = wx_data.get("openid")
    if not openid:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.WX_OPENID_NOT_FOUND
        )

    # ---------------------------------------------------------
    # 4. 数据库查询与用户自动注册 (单表架构)
    # ---------------------------------------------------------
    user = db.query(UserModel).filter(UserModel.openid == openid).first()

    if not user:
        # A. 创建微信账号基本数据 (UserModel)
        user = UserModel(
            openid=openid,
            nickname="手机店员",
            role="staff",
        )
        db.add(user)
        db.flush()  # 拿到 user.id

        # B. 默认绑定体验店铺 (StaffModel 单表直接包含 shop_id 与 role)
        staff = StaffModel(
            user_id=user.id,
            shop_id=1,                            # 体验店铺 ID
            name="手机店员",
            role="staff",                         # 职务角色
            status=1                              # 1: 在职/激活
        )
        db.add(staff)

        try:
            db.commit()
            db.refresh(user)
            db.refresh(staff)
        except Exception as e:
            db.rollback()
            raise BusinessException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"注册用户失败: {str(e)}"
            )
    else:
        # B. 老用户登录：获取其最新绑定的 StaffModel 档案
        staff = db.query(StaffModel).filter(
            StaffModel.user_id == user.id,
            StaffModel.status == 1  # 优先查找在职档案
        ).order_by(StaffModel.id.desc()).first()

    # ---------------------------------------------------------
    # 5. 签发 Token 并组装回传
    # ---------------------------------------------------------
    access_token = create_access_token(
        data={"sub": str(user.id),  "openid": openid}
    )

    # 安全处理字段防护，避免未绑定店铺时报错
    current_shop_id = staff.shop_id if staff else 1
    staff_name = staff.name if staff else (getattr(user, "nickname", "手机店员"))
    staff_role = staff.role if staff else "staff"
    staff_id = staff.id if staff else user.id

    return LoginResponse(
        token=access_token,
        user_info=UserResponse(
            id=staff_id,                          # 返回员工档案 ID (或账号 ID)
            nickname=staff_name,                  # 员工姓名
            role=staff_role,                      # 在店铺中的角色 (如 owner/manager/staff)
            phone=getattr(user, "phone", None),
            avatar_url=getattr(user, "avatar_url", None),
            shop_id=current_shop_id               # 默认关联店铺 ID
        )
    )


# ──────── 🌟 获致当前登录使用者资讯 API (单表架构重构版) ────────
@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前登录使用者资讯",
)
async def get_my_info(
    x_shop_id: int = Header(..., alias="X-Shop-Id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),  # 🌟 依赖微信账号 User
):
    # 💡 打印请求参数与 current_user 资讯
    logger.info(
        f"[get_my_info] 收到请求 | Header X-Shop-Id: {x_shop_id} | "
        f"current_user.id (User): {current_user.id}"
    )

    # ---------------------------------------------------------
    # 1. 单表查询当前用户在目标店铺的履职档案 (StaffModel)
    # ---------------------------------------------------------
    staff_profile = (
        db.query(StaffModel)
        .filter(
            StaffModel.user_id == current_user.id,
            StaffModel.shop_id == x_shop_id,
            StaffModel.status == 1,  # 必须是在职/激活状态
        )
        .first()
    )

    # ---------------------------------------------------------
    # 2. 查无在职档案时的防御与日志排查
    # ---------------------------------------------------------
    if not staff_profile:
        logger.warning(
            f"[get_my_info] 查无在职档案! 尝试排查是否存在非激活档案 -> "
            f"StaffModel(user_id={current_user.id}, shop_id={x_shop_id})"
        )

        # 💡 辅助排查：是否在数据库中有记录，但状态不是 1 (例如 0:待绑定, 2:已禁用)
        any_profile = (
            db.query(StaffModel)
            .filter(
                StaffModel.user_id == current_user.id,
                StaffModel.shop_id == x_shop_id,
            )
            .first()
        )

        if any_profile:
            logger.warning(
                f"[get_my_info] 注意：找到员工档案但状态不符！"
                f"目前 status={any_profile.status} (需要 1)"
            )
        else:
            logger.warning(
                f"[get_my_info] 注意：数据库完全不存在 user_id={current_user.id} 与 shop_id={x_shop_id} 的档案记录！"
            )

        raise BusinessException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NOT_SHOP_MEMBER",
            detail="您不是该店铺的成员或账号已被停用/未激活",
        )

    logger.info(
        f"[get_my_info] 成功查到档案 | shop_id: {staff_profile.shop_id} | "
        f"staff_id: {staff_profile.id} | role: {staff_profile.role} | status: {staff_profile.status}"
    )

    # ---------------------------------------------------------
    # 3. 组合并回传数据
    # ---------------------------------------------------------
    return UserResponse(
        id=staff_profile.id,                            # 返回 Staff 档案 ID
        nickname=staff_profile.name,                    # 员工姓名
        role=staff_profile.role,                        # 该店下的角色 (owner/manager/staff)
        admin_role=getattr(current_user, "role", "staff"),
        phone=getattr(current_user, "phone", None) or staff_profile.phone,
        avatar_url=getattr(current_user, "avatar_url", None) or staff_profile.avatar,
        shop_id=x_shop_id,
        created_at=staff_profile.created_at.isoformat(),
        default_shop_id=getattr(current_user, "default_shop_id", 1),
        default_staff_id=getattr(current_user, "default_staff_id", 1)
    )




@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="修改当前登录用户信息"
)
def update_my_info(
    user_in: UserUpdateSchema,
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前店铺ID"),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改当前登录人的基本信息（包含默认店铺/身份、手机号、昵称、头像）"""
    update_data = user_in.model_dump(exclude_unset=True)

    # 1. 校验是否有传要修改的字段
    if not update_data:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NO_UPDATE_FIELDS_PROVIDED",
            detail="请提供需要更新的字段"
        )

    user_updated = False
    staff_updated = False

    # 🌟 2. 处理设置默认店铺与默认员工身份 (存 User 表)
    # 独立处理，不强依赖 header 中的 X-Shop-Id
    if "default_shop_id" in update_data and update_data["default_shop_id"] is not None:
        target_default_shop_id = update_data["default_shop_id"]
        target_default_staff_id = update_data.get("default_staff_id")

        # 校验选中的店铺/员工身份是否真正属于当前用户
        staff_query = db.query(StaffModel).filter(
            StaffModel.user_id == current_user.id,
            StaffModel.shop_id == target_default_shop_id,
            StaffModel.status == 1
        )
        if target_default_staff_id:
            staff_query = staff_query.filter(StaffModel.id == target_default_staff_id)

        target_default_staff = staff_query.first()
        if not target_default_staff:
            raise BusinessException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_DEFAULT_SHOP",
                detail="您不属于该店铺或员工身份无效，无法设为默认"
            )

        # 真正写入 sys_user 表
        if hasattr(current_user, "default_shop_id"):
            current_user.default_shop_id = target_default_shop_id
            user_updated = True
            
        if hasattr(current_user, "default_staff_id"):
            current_user.default_staff_id = target_default_staff.id
            user_updated = True

    # 🌟 3. 查找当前操作上下文的员工档案 (用于更新当前店铺下的个人信息，如昵称、手机号)
    target_shop_id = x_shop_id or getattr(current_user, "default_shop_id", None) or 1
    staff = db.query(StaffModel).filter(
        StaffModel.user_id == current_user.id,
        StaffModel.shop_id == target_shop_id,
        StaffModel.status == 1  # 确保在职
    ).first()

    # 4. 处理手机号更新（同步更新 User 表 与 当前 Staff 表）
    if "phone" in update_data and update_data["phone"] is not None:
        new_phone = update_data["phone"]
        
        if hasattr(current_user, "phone"):
            current_user.phone = new_phone
            user_updated = True

        if staff and hasattr(staff, "phone"):
            staff.phone = new_phone
            staff_updated = True

    # 5. 处理头像更新 (存 User 表)
    if "avatar_url" in update_data and update_data["avatar_url"] is not None:
        if hasattr(current_user, "avatar_url"):
            current_user.avatar_url = update_data["avatar_url"]
            user_updated = True

    # 6. 处理员工姓名/昵称更新 (存 Staff 表)
    new_name = update_data.get("nickname") or update_data.get("name")
    if new_name is not None and staff:
        staff.name = new_name
        staff_updated = True

    # 7. 提交数据库事务
    try:
        if user_updated:
            db.add(current_user)
        if staff_updated and staff:
            db.add(staff)
            
        if user_updated or staff_updated:
            db.commit()
            if user_updated: 
                db.refresh(current_user)
            if staff_updated and staff: 
                db.refresh(staff)
            
    except Exception as e:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="UPDATE_USER_FAILED",
            detail=f"更新用户信息失败: {str(e)}"
        )

    # 8. 安全获取属性并组装返回
    staff_phone = getattr(staff, "phone", None) or getattr(current_user, "phone", None)
    avatar = getattr(current_user, "avatar_url", None) or (getattr(staff, "avatar", None) if staff else None)
    default_shop_id = getattr(current_user, "default_shop_id", None) or target_shop_id
    dt_obj = staff.created_at if staff else getattr(current_user, "created_at", None)

    return UserResponse(
        id=staff.id if staff else current_user.id,
        nickname=staff.name if staff else getattr(current_user, "nickname", "--"),
        role=staff.role if staff else getattr(current_user, "role", "staff"),
        admin_role=getattr(current_user, "role", "staff"),
        phone=staff_phone,
        avatar_url=avatar,
        shop_id=target_shop_id,
        default_shop_id=default_shop_id,
        created_at=dt_obj.isoformat() if dt_obj else None
    )
