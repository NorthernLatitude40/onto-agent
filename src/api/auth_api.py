import jwt
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.common.database import get_db
from src.model.user_model import User
from src.config.config import WX_APP_ID, WX_APP_SECRET, JWT_SECRET_KEY
from sqlalchemy.ext.asyncio import AsyncSession
from src.model.schema import UserUpdateSchema

router = APIRouter(prefix="/api/v1/auth", tags=["认证鉴权"])

# ⚙️ 微信小程序配置 (实际项目中写在 .env 或 settings.py 里) 
WX_APP_ID = WX_APP_ID
WX_APP_SECRET = WX_APP_SECRET
JWT_SECRET_KEY = JWT_SECRET_KEY
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # Token 有效期 7 天


class WxLoginPayload(BaseModel):
    code: str

# FastAPI 的 Bearer Token 提取器
security = HTTPBearer()

def create_access_token(data: dict):
    """生成 JWT Token"""
    to_encode = data.copy()
    expire = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    【核心中间件】验证 Header 中的 Token，并返回当前登录的用户对象
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证已过期或无效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解密 Token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    # 查库校验用户是否存在
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
        
    return user


@router.post("/wx-login", summary="微信小程序登录/注册")
async def wx_login(payload: WxLoginPayload, db: Session = Depends(get_db)):
    code = payload.code
    if not code:
        raise HTTPException(status_code=400, detail="code 不能为空")

    # 1. 向微信服务器发起换取 session 的请求
    wx_url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": WX_APP_ID,
        "secret": WX_APP_SECRET,
        "js_code": code,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(wx_url, params=params)
        wx_data = resp.json()

    # 2. 检查微信返回结果
    if "errcode" in wx_data and wx_data["errcode"] != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信登录失败: {wx_data.get('errmsg', '未知错误')}"
        )

    openid = wx_data.get("openid")
    session_key = wx_data.get("session_key") # 敏感数据，可暂存 redis

    if not openid:
        raise HTTPException(status_code=400, detail="未获取到 OpenID")

    # 3. 查询数据库中是否存在该 OpenID 的用户
    user = db.query(User).filter(User.openid == openid).first()

    # 如果是新用户，自动完成注册
    if not user:
        user = User(
            openid=openid,
            nickname="手机店员", # 初始默认名称
            role="staff"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 4. 签发自己的 JWT Token
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "openid": openid})

    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "token": access_token,
            "user_info": {
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "role": user.role
            }
        }
    }

@router.get("/me", summary="获取当前登录用户信息")
async def get_my_info(current_user: User = Depends(get_current_user)):
    """测试 Token 保护的接口"""
    return {
        "code": 200,
        "data": {
            "id": current_user.id,
            "nickname": current_user.nickname,
            "role": current_user.role
        }
    }

@router.put("/me", summary="修改当前登录用户信息")
async def update_my_info(
    user_in: UserUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)  # 或 Synchronous Session
):
    """
    修改当前登录人的基本信息（昵称、头像、手机号）
    """
    # 过滤出前端显式传递（非 None）的字段
    update_data = user_in.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="请至少提供一个要修改的字段"
        )
    
    # 动态将属性写入 current_user 对象
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "code": 200,
        "message": "修改成功",
        "data": {
            "id": current_user.id,
            "nickname": current_user.nickname,
            "avatar_url": current_user.avatar_url,
            "phone": current_user.phone,
            "role": current_user.role
        }
    }