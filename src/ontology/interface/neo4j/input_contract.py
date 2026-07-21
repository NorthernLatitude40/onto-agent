from pydantic import BaseModel
from typing import List
from ontology.interface.ontology.output_contract import MappingRule
from ontology.interface.dataset import TableDataset  # 引用統一數據源


class Neo4jBuilderInput(BaseModel):
    mapping_rules: List[MappingRule]
    dataset: TableDataset  # 核心：直接注入標準化後的資料集
