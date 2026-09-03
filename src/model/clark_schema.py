from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from src.common.dict import ShopRole

# 1. 修改員工資訊請求
class StaffUpdateSchema(BaseModel):
    id: int
    name: Optional[str] = Field(None, max_length=64, description="員工姓名/備註")
    role: Optional[ShopRole] = Field(None, description="角色: owner/manager/staff")
        # 僅允許傳入 1 (正常) 或 2 (禁用/離職)
    status: Optional[int] = Field(None, description="狀態: 1-正常在職, 2-已離職/禁用")


class StaffResponse(BaseModel):
    """创建/获取员工信息的返回数据结构 (Bare Payload)"""
    id: int
    nickname: str
    role: str
    status: int
    is_active: bool = False

    # 兼容 ORM 模型自动转换
    model_config = ConfigDict(from_attributes=True, extra="ignore")


# ==========================================
# 1. 设置默认店铺/身份 请求体 (Request Body)
# ==========================================
class SetDefaultIdentitySchema(BaseModel):
    default_shop_id: int = Field(
        ..., 
        description="默认店铺 ID", 
        example=1, 
        gt=0
    )
    default_staff_id: int = Field(
        ..., 
        description="默认员工身份 ID (Staff ID)", 
        example=26, 
        gt=0
    )

    class Config:
        json_schema_extra = {
            "example": {
                "default_shop_id": 1,
                "default_staff_id": 26
            }
        }


# ==========================================
# 2. 设置默认店铺/身份 响应体 (Response Body)
# ==========================================
class SetDefaultIdentityResponse(BaseModel):
    code: int = Field(200, description="状态码", example=200)
    message: str = Field("默认身份设置成功", description="提示信息")
    data: Optional[dict] = Field(None, description="返回数据，无特殊需返回则为 null")