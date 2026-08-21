# app/core/exceptions.py
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from src.model.rfc_7807_schema import ProblemDetails

from src.common.i18n import get_i18n_message
from src.common.logger import get_logger

# ⚙️ 獲取當前模組的 logger
logger = get_logger("API_SERVICE")


# ==============================================================================
# 1. RFC 7807 業務異常類定義
# ==============================================================================
class BusinessException(Exception):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "BAD_REQUEST",
        detail: Optional[str] = None,  # 可選，不傳時會自動查 i18n 字典
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
            detail=detail,
        )


class UnauthorizedException(BusinessException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            detail=detail,
        )


# ==============================================================================
# 2. 全局異常處理註冊邏輯 (包含動態翻譯與完整的 Log 記錄)
# ==============================================================================
def register_exception_handlers(app: FastAPI) -> None:

    # 1. 業務自定義異常（帶國際化與警告/錯誤 Log）
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        # 💡 記錄 Log：5xx 當作 Error，4xx 當作 Warning 並記錄堆棧
        log_msg = f"[BusinessException] Path: {request.url.path} | Status: {exc.status_code} | Code: {exc.code} | Detail: {exc.detail}"
        if exc.status_code >= 500:
            logger.error(log_msg, exc_info=True)
        else:
            logger.warning(log_msg, exc_info=True)

        # 💡 從 Header 獲取客戶端語言
        accept_language = request.headers.get("Accept-Language")

        # 💡 動態翻譯 detail 文本
        localized_detail = get_i18n_message(
            code=exc.code,
            accept_language=accept_language,
            fallback_detail=exc.detail,
        )

        problem_details = ProblemDetails(
            type=exc.type_url,
            title=exc.code,
            status=exc.status_code,
            detail=localized_detail,
            instance=str(request.url.path),
            **exc.extra,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=problem_details.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    # 2. HTTP 顯式異常（如 404、401、403 等框架或顯式拋出的 HTTPException）
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 💡 記錄 HTTP 異常堆棧
        logger.warning(
            f"[HTTPException] Path: {request.url.path} | Status: {exc.status_code} | Detail: {exc.detail}",
            exc_info=True,
        )

        problem_details = ProblemDetails(
            type="about:blank",
            title="HTTP_ERROR",
            status=exc.status_code,
            detail=str(exc.detail),
            instance=str(request.url.path),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem_details.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    # 3. 請求參數校驗異常（422 Unprocessable Entity）
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        # 💡 記錄校驗失敗的詳細參數與堆棧信息
        logger.warning(
            f"[RequestValidationError] Path: {request.url.path} | Errors: {exc.errors()}",
            exc_info=True,
        )

        problem_details = ProblemDetails(
            type="about:blank",
            title="VALIDATION_ERROR",
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Input validation failed.",
            instance=str(request.url.path),
            invalid_params=exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=problem_details.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    # 4. 終極兜底異常（未預期的系統崩潰，如 500 代碼 Bug）
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # 💡 使用 logger.error 並加上 exc_info=True 打印完整 Traceback
        logger.error(
            f"[UnhandledException] Path: {request.url.path} | Exception: {exc}",
            exc_info=True,
        )

        problem_details = ProblemDetails(
            type="about:blank",
            title="INTERNAL_SERVER_ERROR",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred. Please try again later.",
            instance=str(request.url.path),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=problem_details.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )