from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# 基礎 Schema
class PartnerBase(BaseModel):
    name: str = Field(..., max_length=50, description="姓名/單位名稱")
    phone: Optional[str] = Field(None, max_length=20, description="聯繫電話")
    type: int = Field(1, ge=1, le=3, description="類型：1-客戶 2-供應商 3-二者皆是")
    remark: Optional[str] = Field(None, max_length=255, description="備註")

# 創建 Partner 請求體
class PartnerCreate(PartnerBase):
    pass

# Partner 響應模型
class PartnerResponse(PartnerBase):
    id: int
    receivable_amount: float
    payable_amount: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 統一 API 響應包裹格式
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[dict | list | PartnerResponse] = None