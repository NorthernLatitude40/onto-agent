
from pydantic import BaseModel

from ontology.interface.dataset import DataFieldSchema  # 引用統一欄位定義


class DatasetSchemaInput(BaseModel):
    source_id: str
    dataset_name: str
    fields: list[DataFieldSchema]  # 統一由 Dataset 提供欄位資訊
