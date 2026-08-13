# app/core/exceptions.py
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from src.model.rfc_7807_schema import ProblemDetails

from src.common.i18n import get_i18n_message


# ==============================================================================
# 1. RFC 7807 业务异常类定义
# ==============================================================================
class BusinessException(Exception):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "BAD_REQUEST",
        detail: Optional[str] = None,  # 可选，不传时会自动查 i18n 字典
        type_url: str = "about:blank",
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.type_url = type_url
        self.extra = extra or {}


class PermissionDeniedException(BusinessException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PERMISSION_DENIED",
            detail=detail
        )


class UnauthorizedException(BusinessException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            detail=detail
        )


# ==============================================================================
# 2. 全局异常处理注册逻辑 (包含动态翻译)
# ==============================================================================
def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        # 💡 从 Header 获取客户端语言
        accept_language = request.headers.get("Accept-Language")
        
        # 💡 动态翻译 detail 文本
        localized_detail = get_i18n_message(
            code=exc.code,
            accept_language=accept_language,
            fallback_detail=exc.detail
        )

        problem_details = ProblemDetails(
            type=exc.type_url,
            title=exc.code,
            status=exc.status_code,
            detail=localized_detail,  # 输出自动翻译后的结果
            instance=str(request.url.path),
            **exc.extra  # 或 extensions=exc.extra
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=problem_details.model_dump(
                exclude_none=True
            ),  # Pydantic v2 用 model_dump，v1 用 .dict()
            media_type="application/problem+json",
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):

        problem_details = ProblemDetails(
            type="about:blank",
            title="HTTP_ERROR",
            status=exc.status_code,
            detail=exc.detail,
            instance=str(request.url.path)
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem_details.model_dump(
                exclude_none=True
            ),  # Pydantic v2 用 model_dump，v1 用 .dict()
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):

        problem_details = ProblemDetails(
            type="about:blank",
            title="VALIDATION_ERROR",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Input validation failed.",
            instance=str(request.url.path),
            invalid_params=exc.errors()
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem_details.model_dump(
                exclude_none=True
            ),  # Pydantic v2 用 model_dump，v1 用 .dict()
            media_type="application/problem+json",
        )