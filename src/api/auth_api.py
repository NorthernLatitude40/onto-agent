from datetime import datetime, timedelta, timezone
from typing import List

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

# 根据你的实际项目路径导入
from src.common.database import get_db
from src.config.config import settings
from src.model.schema import UserUpdateSchema
from src.model.user_model import User
from src.model.schema import UserOutSchema, TokenOutSchema, UserUpdateSchema
from src.model.response_models import LoginResponse, UserResponse
from src.common.exceptions import BusinessException
from src.model.staff_model import StaffModel
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM

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


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """【核心依赖】解析 Token 并获取当前登录用户对象"""
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

    # 注意：确保查询时 ID 类型与数据库字段类型一致
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


class PermissionChecker:
    """RBAC 权限检查器"""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
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

@router.post(
    "/wx-login", 
    response_model=LoginResponse, 
    status_code=status.HTTP_200_OK,
    summary="微信小程序登录/注册"
)
async def wx_login(payload: WxLoginPayload, db: Session = Depends(get_db)):
    # 1. 校验 Code
    if not payload.code.strip():
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WX_CODE_EMPTY"
        )

    # 2. 请求微信接口换取 session_key 和 openid
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
        
    # 3. 检查微信 API 返回状态
    if wx_data.get("errcode", 0) != 0:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WX_LOGIN_FAILED",
            # 如果想在调试日志中保留微信原生 errmsg，可以放在 extra 里，RFC 7807 会自动序列化输出
            extra={"wx_errmsg": wx_data.get("errmsg")} 
        )

    openid = wx_data.get("openid")
    if not openid:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WX_OPENID_NOT_FOUND"
        )

    # 4. 数据库查询与用户注册
    user = db.query(User).filter(User.openid == openid).first()

    if not user:
        user = User(
            openid=openid,
            nickname="手机店员",
            role="staff",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 5. 签发 Token
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "openid": openid}
    )

    return LoginResponse(
        token=access_token,
        user_info=user
    )


@router.get(
    "/me", 
    response_model=UserResponse, 
    status_code=status.HTTP_200_OK,
    summary="获取当前登录用户信息"
)
async def get_my_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):

    staff_rel = db.query(StaffModel).filter(
        StaffModel.user_id == current_user.id
    ).first()
    if staff_rel:
        current_user.nickname = staff_rel.name
        current_user.role = staff_rel.role
    return current_user

@router.put(
    "/me", 
    response_model=UserResponse, 
    status_code=status.HTTP_200_OK,
    summary="修改当前登录用户信息"
)
def update_my_info(
    user_in: UserUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改当前登录人的基本信息（手机号存 User 表，姓名/备注存 shop_staff 表）"""
    update_data = user_in.model_dump(exclude_unset=True)

    # 1. 校验是否有传要修改的字段
    if not update_data:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NO_UPDATE_FIELDS_PROVIDED"
        )

    user_updated = False
    staff_updated = False

    # 2. 更新 User 表（手机号）
    if "phone" in update_data:
        new_phone = update_data.pop("phone")
        
        existing = db.query(User).filter(User.phone == new_phone, User.id != current_user.id).first()
        if existing:
            raise BusinessException(status_code=400, code="PHONE_EXISTS", message="该手机号已被使用")
            
        current_user.phone = new_phone
        user_updated = True

    # 3. 更新 StaffModel 表（姓名/备注 name）
    if "nickname" in update_data:
        new_name = update_data.pop("nickname")
        
        # 从 current_user.staff_profiles (根据关系获取) 中拿到当前店铺的员工记录
        # 如果用户只绑定了一个店铺，可以直接拿第一条；如果有多店铺，可根据当前上下文的 shop_id 过滤
        staff_info = None
        if hasattr(current_user, "staff_profiles") and current_user.staff_profiles:
            # 找到状态正常的 staff 记录（或者你可以加上 current_shop_id 过滤）
            staff_info = next((s for s in current_user.staff_profiles if s.status == 1), current_user.staff_profiles[0])
        
        if not staff_info:
            # 如果没有查到 relationship 关联，直接去数据库查
            staff_info = db.query(StaffModel).filter(StaffModel.user_id == current_user.id).first()

        if staff_info:
            staff_info.name = new_name
            db.add(staff_info)
            staff_updated = True

    # 4. 提交数据库事务
    try:
        if user_updated:
            db.add(current_user)
            
        db.commit()
        db.refresh(current_user)
        
    except Exception as e:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="UPDATE_USER_FAILED",
            message=f"更新用户信息失败: {str(e)}"
        )

    return current_user