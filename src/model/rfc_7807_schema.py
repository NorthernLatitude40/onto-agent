from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ProblemDetails(BaseModel):
    """遵循 RFC 7807 规范的错误响应实体"""
    type: str = Field(
        default="about:blank", 
        description="描述问题类型的 URI (如: https://api.shop.com/errors/device-not-found)"
    )
    title: str = Field(description="简短的人类可读的问题摘要")
    status: int = Field(description="HTTP 状态码")
    detail: str = Field(description="针对当前具体问题的详细说明")
    instance: Optional[str] = Field(
        default=None, 
        description="发生此特定问题的 URI 引用"
    )
    # 扩展字段：用于携带具体业务数据（如需要澄清的设备列表）
    extensions: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="附加扩展数据"
    )

    class Config:
        extra = "allow"  # 🌟 允许任意动态扩展字段（如 candidate, queried_id 等）