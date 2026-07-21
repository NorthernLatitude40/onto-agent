from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional


# 1. Ontology 定義
class ConceptNode(BaseModel):
    id: str
    label: str
    description: Optional[str] = None


class RelationshipEdge(BaseModel):
    id: str
    source: str  # 對應 ConceptNode.id
    target: str  # 對應 ConceptNode.id
    type: str


class OntologySchema(BaseModel):
    concepts: List[ConceptNode]
    relationships: List[RelationshipEdge]


# 2. 映射規則定義
class NodeMapping(BaseModel):
    concept_id: str = Field(..., description="知識圖譜中的本體概念ID，例如 'ns0__VIPCustomer'")
    primary_key: str = Field(..., description="Excel 表格中對應的欄位名稱，例如 'customer_id'")
    properties: Dict[str, str] = Field(default_factory=dict, description="其他要映射的屬性對照表")


class EdgeMapping(BaseModel):
    relationship_id: str
    source_key: str
    target_key: str
    properties: Dict[str, str]


# 3. 核心修正：將 List[dict] 升級為強型態，並確保別名相容
class MappingRule(BaseModel):
    source_sheet: str

    # 💡 1. 將型態從 List[dict] 改為 List[NodeMapping]
    # 💡 2. validation_alias 負責攔截 Agent 亂吐的舊欄位
    # 💡 3. serialization_alias 負責讓 model_dump() 匯出時保持你後端要的欄位名
    map_to_node: Optional[List[NodeMapping]] = Field(
        default=None,
        validation_alias="node_mappings",
        serialization_alias="map_to_node",
    )

    map_to_edge: Optional[List[EdgeMapping]] = Field(
        default=None,
        validation_alias="relationship_mappings",
        serialization_alias="map_to_edge",
    )

    # 💡 Pydantic v2 的標準配置寫法
    model_config = ConfigDict(populate_by_name=True)  # 允許初始化時同時認得別名與原名


# 4. 總輸出契約
class OntologyBuilderOutput(BaseModel):
    ontology_version: str
    ontology: OntologySchema
    mapping_rules: List[MappingRule]
