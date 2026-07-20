from pydantic import BaseModel, Field
from typing import List


class DesignItem(BaseModel):
    no: int = Field(..., alias="No", description="序号")
    item_name: str = Field(..., alias="项目名称", description="项目名称")
    category: str = Field(..., alias="分类", description="分类")
    required: str = Field(..., alias="必须", description="是否必须")
    field_code: str = Field(..., alias="栏目号码", description="栏目号码")
    format: str = Field(..., alias="格式", description="格式")
    table: str = Field(..., alias="表格", description="表格")
    field_name: str = Field(..., alias="栏域", description="栏域")
    remarks: str = Field(..., alias="備考", description="备注")


class DesignDocument(BaseModel):
    items: List[DesignItem] = Field(..., description="详细设计书条目列表")
