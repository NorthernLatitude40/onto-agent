# src/common/exception_handlers.py
import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.common.exceptions import BusinessException

logger = logging.getLogger("API_SERVICE")


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    # 1. 捕获自定义业务异常
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        logger.warning(
            f"⚠️ [业务异常] Path: {request.url.path} | Code: {exc.code} | Msg: {exc.message}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
            },
        )

    # 2. 捕获 FastAPI / Starlette 的 HTTP 异常 (如 401, 403, 404)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(
            f"⚠️ [HTTP 异常] Path: {request.url.path} | Status: {exc.status_code} | Detail: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": str(exc.detail),
                "data": None,
            },
        )

    # 3. 捕获 Pydantic 请求参数校验异常 (422 Unprocessable Entity)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        # 提取第一个不合规字段的错误提示
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        field = ".".join([str(loc) for loc in first_error.get("loc", [])])
        msg = first_error.get("msg", "参数格式错误")
        detail_msg = f"参数校验失败: [{field}] {msg}"

        logger.warning(f"⚠️ [参数校验错误] Path: {request.url.path} | {detail_msg}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": 400,
                "message": detail_msg,
                "data": None,
            },
        )

    # 4. 兜底捕获所有未预期的未知系统异常 (防止泄露敏感堆栈并记录日志)
    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"❌ [未捕获系统致命异常] Path: {request.url.path} | Error: {exc}",
            exc_info=True,  # 将完整 Stack Trace 写入日志，方便 Docker / Render 查错
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": 500,
                "message": "服务器内部错误，请联系管理员",
                "data": None,
            },
        )