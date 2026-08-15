from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from src.common.dict import ShopRole

class UserUpdateSchema(BaseModel):
    nickname: Optional[str] = Field(None, max_length=64, description="用户昵称")
    avatar_url: Optional[str] = Field(None, max_length=255, description="头像URL")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    default_shop_id: Optional[int] = Field(None, description="默认店铺ID")
    default_staff_id: Optional[int] = None



# 1. 管理员新增员工请求
class CreateStaffRequest(BaseModel):
    nickname: str = Field(..., description="员工姓名/备注")
    phone: Optional[str] = Field(None, description="手机号")
    role: ShopRole = Field(ShopRole.STAFF, description="角色: manager/staff")

# 2. 生成邀请 Token 请求
class CreateInviteRequest(BaseModel):
    shop_id: int = Field(..., alias="shopId")
    staff_id: int = Field(..., alias="user_id") # 自动把前端传的 user_id 映射为 staff_id

    class Config:
        populate_by_name = True

# 3. 员工接受邀请请求
class AcceptInviteRequest(BaseModel):
    code: str
    invite_token: Optional[str] = None  # 🌟 改為可選
    shop_id: Optional[int] = None       # 🌟 改為可選

class UserOutSchema(BaseModel):
    id: int
    nickname: str
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    role: str

    # 允许从 SQLAlchemy ORM 对象直接读取属性填充模型
    model_config = ConfigDict(from_attributes=True)


class TokenOutSchema(BaseModel):
    token: str
    user_info: UserOutSchema