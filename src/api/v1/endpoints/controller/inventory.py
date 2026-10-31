from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.inspection import inspect
from src.common.database import engine, Base  # 假設你的 SQLAlchemy engine 在這裏
# 導入你的 Model，例如 InventoryModel
from src.model.pricing_inventory_model import PricingInventoryModel
from src.model.van_vehicle_model import VanModel

router = APIRouter(prefix="/metadata", tags=["Metadata"])


@router.get("/tables/{table_name}/columns")
def get_table_columns(table_name: str):
    """動態獲取指定數據表的字段結構"""
    # 建立表名字典映射（安全起見，避免直接用字串反射任意表）
    table_map = {
        "pricing_inventory": PricingInventoryModel,
        "van_vehicles": VanModel,
        # 其他表...
    }

    model = table_map.get(table_name)
    if not model:
        raise HTTPException(status_code=404, detail="Table not found")

    # 使用 SQLAlchemy inspect 獲取字段資訊
    mapper = inspect(model)
    columns_info = []

    for column in mapper.columns:
        columns_info.append({
            "name": column.key,                        # 字段名
            "type": str(column.type),                  # 數據類型
            "nullable": column.nullable,               # 是否允許 NULL
            "primary_key": column.primary_key,         # 是否為主鍵
            "default": str(column.default.arg) if column.default else None,  # 默認值
        })

    return {
        "table_name": table_name,
        "columns": columns_info
    }