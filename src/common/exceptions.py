# src/common/exceptions.py
from typing import Any, Optional


class BusinessException(Exception):
    """自定义业务逻辑异常"""

    def __init__(
        self,
        message: str = "业务处理异常",
        code: int = 400,
        data: Optional[Any] = None,
        status_code: int = 200,  # HTTP 状态码（通常设为 200 或 400）
    ):
        self.message = message
        self.code = code
        self.data = data
        self.status_code = status_code
        super().__init__(self.message)