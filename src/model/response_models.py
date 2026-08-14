from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, timedelta, timezone



class UserResponse(BaseModel):
    """当前用户信息返回模型 (Bare Payload)"""
    id: int
    nickname: str
    role: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    shop_id: int

    # 💡 必须配置：允许 Pydantic 直接从 SQLAlchemy ORM 对象读取数据
    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    """微信登录成功返回的标准模型"""
    token: str
    user_info: UserResponse

    model_config = ConfigDict(from_attributes=True)

class UserUpdateSchema(BaseModel):
    """更新用户信息请求模型"""
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None

