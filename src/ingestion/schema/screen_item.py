from pydantic import BaseModel, Field, ConfigDict
from typing import List


class DesignItem(BaseModel):
    # 啟用 populate_by_name，允許同時接收 python 欄位名 (no) 與 alias 名 (No)
    model_config = ConfigDict(populate_by_name=True)

    no: int = Field(..., alias="No", description="序号")
    item_name: str = Field(..., alias="項目名称", description="項目名称")
    category: str = Field(..., alias="分類", description="分類")
    required: str = Field(..., alias="必須", description="是否必須")
    field_code: str = Field(..., alias="桁数", description="桁数")
    format: str = Field(..., alias="フォーマット", description="フォーマット")
    table: str = Field(..., alias="テーブル", description="テーブル")
    field_name: str = Field(..., alias="フィールド", description="フィールド")
    remarks: str = Field(..., alias="備考", description="備考")


class DesignDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    items: List[DesignItem] = Field(..., description="详细设计书条目列表")
