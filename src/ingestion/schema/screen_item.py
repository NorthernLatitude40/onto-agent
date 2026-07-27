# src/ingestion/schema/screen_item.py

from pydantic import BaseModel, Field


class DesignItem(BaseModel):
    # 將所有欄位宣告為嚴格包含（預設值改在欄位定義上，但強制 JSON 包含 Key）
    no: int | None = Field(default=None, description="序號")
    item_name: str = Field(..., description="項目名稱 (Canonical: item_name)")
    category: str = Field(..., description="分類 (Canonical: category)")
    required: str = Field(default="N", description="是否必須 (Y/N)")
    field_code: str = Field(default="", description="桁數/長度")
    format: str = Field(default="", description="格式")
    table: str = Field(default="", description="DB Table")
    field_name: str = Field(default="", description="DB Field")
    remarks: str = Field(default="", description="備考")
    is_group: bool = Field(
        default=False,
        description="是否為群組標題列；為 True 時 Excel 匯出會合併整列、僅顯示 item_name",
    )

    @classmethod
    def model_json_schema(cls, **kwargs):
        """覆寫 JSON Schema 產生邏輯，強制將所有欄位列入 required 陣列，約束 LLM 必須輸出所有 Key。"""
        schema = super().model_json_schema(**kwargs)
        # 強制指定 items 內的所有 properties 均為 required
        schema["required"] = list(schema.get("properties", {}).keys())
        return schema


class DesignDocument(BaseModel):
    items: list[DesignItem]