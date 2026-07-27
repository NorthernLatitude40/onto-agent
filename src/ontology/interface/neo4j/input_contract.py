
from pydantic import BaseModel

from ontology.interface.dataset import TableDataset  # 引用統一數據源
from ontology.interface.ontology.output_contract import MappingRule


class Neo4jBuilderInput(BaseModel):
    mapping_rules: list[MappingRule]
    dataset: TableDataset  # 核心：直接注入標準化後的資料集
