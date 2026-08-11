from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi import status

# 定义泛型，方便 Pydantic 生成精准的 API Schema 类型
T = TypeVar("T")

class ResponseModel(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class Res:
    """响应工具类，用于快速构建返回对象"""
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", code: int = 200) -> dict:
        return {
            "code": code,
            "message": message,
            "data": data
        }

    @staticmethod
    def fail(message: str = "操作失败", code: int = 400, data: Any = None) -> dict:
        return {
            "code": code,
            "message": message,
            "data": data
        }