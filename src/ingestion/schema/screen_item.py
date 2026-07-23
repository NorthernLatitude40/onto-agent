# screen_item.py
"""
變更說明（相對於原版）：
  新增 is_group 欄位。tools.py 的 _build_excel 原本就支援「群組標題列」
  （item.get("is_group") 為 True 時整列合併、灰底），但這個標記過去
  不屬於任何 schema，只是隱性依賴 dict 裡剛好有沒有這個 key。
  現在把它變成 DesignItem 的正式欄位（預設 False），design_doc_builder.py
  用它讓「Class」列在 Excel 裡渲染成區塊標題，其餘欄位都是明確可見的 canonical schema。
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class DesignItem(BaseModel):
    # 核心標準欄位，不受 Excel 表頭文字改變影響
    no: Optional[int] = Field(None, description="序號")
    item_name: str = Field(..., description="項目名稱 (Canonical: item_name)")
    category: str = Field(..., description="分類 (Canonical: category)")
    required: str = Field(default="N", description="是否必須")
    field_code: str = Field(default="", description="桁數/長度")
    format: str = Field(default="", description="格式")
    table: str = Field(default="", description="DB Table")
    field_name: str = Field(default="", description="DB Field")
    remarks: str = Field(default="", description="備考")
    is_group: bool = Field(
        default=False,
        description="是否為群組標題列；為 True 時 Excel 匯出會合併整列、僅顯示 item_name",
    )


class DesignDocument(BaseModel):
    items: List[DesignItem]
