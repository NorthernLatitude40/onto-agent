"""
Test Proxy API Endpoint
Provides a proxy service to bypass browser CORS restrictions for testing purposes
"""

from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel, Field
import httpx
import json
from typing import Optional, Dict, Any

router = APIRouter()

# ==================== Request/Response Models ====================

class TestStepRequest(BaseModel):
    """Configuration for proxy request"""
    url: str = Field(..., description="Target URL to make the request to")
    method: str = Field("GET", description="HTTP method (GET, POST, PUT, DELETE)")
    headers: Optional[Dict[str, Any]] = Field(None, description="Request headers")
    params: Optional[Dict[str, Any]] = Field(None, description="Query parameters for GET requests")
    timeout: Optional[int] = Field(30000, description="Request timeout in milliseconds")

class TestStepResponse(BaseModel):
    """Proxy request response"""
    data: Any = Field(..., description="The actual API response data")
    status_code: int = Field(..., description="HTTP status code from the target API")
    headers: Optional[Dict[str, str]] = Field(None, description="Response headers from the target API")

# ==================== Proxy Endpoints ====================

@router.post(
    "/test-step-request",
    response_model=TestStepResponse,
    status_code=status.HTTP_200_OK,
    summary="测试步骤请求代理",
    description="通过后端代理发送HTTP请求，绕过浏览器的unsafe header限制",
    responses={
        200: {
            "description": "成功返回目标API响应",
            "content": {
                "application/json": {
                    "example": {
                        "data": {"product": {"name": "iPhone 15", "price": 999.00}},
                        "status_code": 200,
                        "headers": {"Content-Type": "application/json"}
                    }
                }
            }
        },
        400: {
            "description": "请求参数无效",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "缺少必填字段: url"
                    }
                }
            }
        },
        500: {
            "description": "代理请求失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "目标API请求超时"
                    }
                }
            }
        }
    }
)
async def test_step_request(proxy_data: TestStepRequest = Body(
    ...,
    description="代理请求配置",
    example={
        "url": "https://api.example.com/products",
        "method": "GET",
        "headers": {"User-Agent": "Mozilla/5.0"},
        "params": {"category": "electronics", "limit": 10},
        "timeout": 30000
    }
)):
    """
    测试步骤请求代理

    该接口通过后端发送HTTP请求，绕过浏览器的unsafe header限制，
    用于测试从步骤1获取真实API数据。

    Args:
        proxy_data: 代理请求配置

    Returns:
        TestStepResponse: 包含目标API响应的完整信息
    """
    try:
        # Validate method
        method = proxy_data.method.upper()
        if method not in ["GET", "POST", "PUT", "DELETE"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的HTTP方法: {proxy_data.method}"
            )

        # Prepare request parameters
        timeout = proxy_data.timeout / 1000.0  # Convert to seconds

        # Make the actual HTTP request using httpx (supports async)
        async with httpx.AsyncClient() as client:
            kwargs = {
                "url": (proxy_data.url or "").strip(),
                "method": method,
                "headers": proxy_data.headers or {},
                "timeout": timeout
            }

            if method == "GET" and proxy_data.params:
                kwargs["params"] = proxy_data.params

            # For non-GET methods, we need to handle the body/data
            if method != "GET":
                # Try to determine if params should be sent as JSON or form data
                if proxy_data.params and isinstance(proxy_data.params, dict):
                    try:
                        # Check if it looks like JSON data
                        json.dumps(proxy_data.params)
                        kwargs["json"] = proxy_data.params
                    except (TypeError, ValueError):
                        # Fallback to form data
                        kwargs["data"] = proxy_data.params

            response = await client.request(**kwargs)

            # Extract response data and headers
            try:
                response_data = response.json()
            except (json.JSONDecodeError, ValueError):
                # If response is not JSON, return as string
                response_data = response.text

            response_headers = dict(response.headers)

            return {
                "data": response_data,
                "status_code": response.status_code,
                "headers": response_headers
            }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="目标API请求超时"
        )
    except httpx.RequestError as e:
        error_msg = str(e)
        if "Connection refused" in error_msg or "Failed to connect" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"无法连接到目标API: {error_msg}"
            )
        elif "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="目标API请求超时"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"代理请求失败: {error_msg}"
            )
    except Exception as e:
        error_msg = str(e)
        if "JSONDecodeError" in error_msg or "Expecting value" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail="目标API返回了非JSON响应，已自动转换为文本"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"代理请求失败: {error_msg}"
            )