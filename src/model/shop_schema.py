from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from src.common.dict import ShopRole
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

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

# ==============================================================================
# 1. 创建店铺请求 Schema (Base & Create)
# ==============================================================================
class ShopBase(BaseModel):
    name: str
    logo: Optional[str] = ""
    contact_name: Optional[str] = ""
    contact_phone: Optional[str] = ""
    province: Optional[str] = ""
    city: Optional[str] = ""
    district: Optional[str] = ""
    address_detail: Optional[str] = ""
    is_active: Optional[bool] = True


class ShopCreateSchema(ShopBase):
    """创建店铺请求体（也可由后端根据 current_user.id 自动填充 owner_id）"""
    owner_id: Optional[int] = None  # 如果是管理员帮别人建店可以显式传，否则默认取当前登录人


# ==============================================================================
# 2. 更新店铺请求 Schema (Update)
# ==============================================================================
class ShopUpdateSchema(BaseModel):
    """更新店铺请求体"""
    owner_id: Optional[int] = None  # 支持转让店铺所有权
    name: Optional[str] = None
    logo: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address_detail: Optional[str] = None
    is_active: Optional[bool] = None


# ==============================================================================
# 3. 店铺响应 Schema (Response)
# ==============================================================================
class ShopResponse(BaseModel):
    """当前店铺信息响应模型 (Bare Payload)"""
    id: int
    owner_id: int
    name: str
    logo: Optional[str] = ""
    contact_name: Optional[str] = ""
    contact_phone: Optional[str] = ""
    province: Optional[str] = ""
    city: Optional[str] = ""
    district: Optional[str] = ""
    address_detail: Optional[str] = ""
    staff_count: int = 1  # 激活员工总数

    model_config = ConfigDict(from_attributes=True)