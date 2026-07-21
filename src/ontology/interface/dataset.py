from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class SourceType(str, Enum):
    EXCEL = "EXCEL"
    CSV = "CSV"
    RELATIONAL_DB = "SQL"
    API = "API"

class DataFieldSchema(BaseModel):
    name: str                           # 欄位/屬性名稱 (例如: "customer_id")
    data_type: str                      # 統一後的型態 (e.g., "STRING", "INTEGER", "FLOAT", "DATETIME")
    raw_type: Optional[str] = None      # 原始資料型態 (e.g., "varchar(50)" 或 "float64")
    is_nullable: bool = True

class TableDataset(BaseModel):
    """
    統一數據源契約：代表一張標準的二維資料表
    """
    dataset_id: str                     # 資料集唯一標識 (e.g., "sales_db_orders")
    source_type: SourceType             # 數據源類型
    table_name: str                     # 表名或 Sheet 名 (e.g., "Orders")
    schema_fields: List[DataFieldSchema]# 欄位定義 (Schema Discovery 直接吃這個)
    rows: List[Dict[str, Any]]          # 實際的行數據 (Neo4j Builder 直接吃這個)
    
    class Config:
        # 允許大型數據集，關閉 Pydantic 的某些嚴格檢查以提升效能
        from_attributes = True