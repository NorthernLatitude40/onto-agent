from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from src.common.dict import ShopRole

# 1. 修改員工資訊請求
class StaffUpdateSchema(BaseModel):
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
    model_config = ConfigDict(from_attributes=True)