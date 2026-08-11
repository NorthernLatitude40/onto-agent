from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from src.model.user_model import UserRole

class UserUpdateSchema(BaseModel):
    nickname: Optional[str] = Field(None, max_length=64, description="用户昵称")
    avatar_url: Optional[str] = Field(None, max_length=255, description="头像URL")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")

# ──────── 商家自主开店/创建店铺 Schema ────────
class CreateShopPayload(BaseModel):
    name: str = Field(..., description="店铺名称", example="苹果专卖店")
    logo: Optional[str] = Field(default="", description="店铺LOGO地址")
    contact_name: Optional[str] = Field(default="", description="联系人姓名")
    contact_phone: Optional[str] = Field(default="", description="联系电话")
    province: Optional[str] = Field(default="", description="省/地区")
    city: Optional[str] = Field(default="", description="城市")
    district: Optional[str] = Field(default="", description="区县")
    address_detail: Optional[str] = Field(default="", description="详细地址")

# ──────── 修改店铺信息 Schema ────────
class UpdateShopPayload(BaseModel):
    shop_id: Optional[int] = Field(None, description="店铺ID（不传默认修改当前用户所属店铺）")
    name: Optional[str] = Field(None, description="店铺名称")
    logo: Optional[str] = Field(None, description="店铺LOGO地址")
    contact_name: Optional[str] = Field(None, description="联系人姓名")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    province: Optional[str] = Field(None, description="省/地区")
    city: Optional[str] = Field(None, description="城市")
    district: Optional[str] = Field(None, description="区县")
    address_detail: Optional[str] = Field(None, description="详细地址")



# 1. 管理员新增员工请求
class CreateStaffRequest(BaseModel):
    nickname: str = Field(..., description="员工姓名/备注")
    phone: Optional[str] = Field(None, description="手机号")
    role: UserRole = Field(UserRole.STAFF, description="角色: manager/staff")

# 2. 生成邀请 Token 请求
class CreateInviteRequest(BaseModel):
    shop_id: int = Field(..., alias="shopId")
    staff_id: int = Field(..., alias="user_id") # 自动把前端传的 user_id 映射为 staff_id

    class Config:
        populate_by_name = True

# 3. 员工接受邀请请求
class AcceptInviteRequest(BaseModel):
    invite_token: str = Field(..., description="邀请Token")

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