
from pydantic import BaseModel, Field


class IORelatedItem(BaseModel):
    no: int = Field(..., alias="No", description="序号")
    logical_name: str = Field(..., alias="論理名称", description="逻辑名称")
    physical_name: str = Field(..., alias="物理名称", description="物理名称")
    io_type: str = Field(..., alias="I/O", description="输入输出类型")
    remarks: str = Field(..., alias="備考", description="备注")


class IORelatedDocument(BaseModel):
    parameter_list: list[IORelatedItem] = Field(..., description="参数一览")
    table_list: list[IORelatedItem] = Field(..., description="表一览")
    file_list: list[IORelatedItem] = Field(..., description="文件一览")