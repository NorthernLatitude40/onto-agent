from pydantic import BaseModel
from typing import List, Optional

class MigrationMetrics(BaseModel):
    nodes_created: int = 0
    relationships_created: int = 0
    properties_set: int = 0
    execution_time_ms: int

class Neo4jBuilderOutput(BaseModel):
    status: str # "SUCCESS" or "FAILED"
    job_id: str
    metrics: Optional[MigrationMetrics] = None
    errors: List[str] = []