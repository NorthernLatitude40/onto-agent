"""
Standardized response models for API endpoints.

This module provides consistent response structures across all API endpoints,
including RFC 7807 compliant error responses and standardized success responses.
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List, Dict, Any
from datetime import datetime

# RFC 7807 Error Types - Standardized across all API endpoints
class ErrorType(str):
    """Standardized error types for RFC 7807 compliance."""
    BAD_REQUEST = "https://api.example.com/errors/bad-request"
    UNAUTHORIZED = "https://api.example.com/errors/unauthorized"
    FORBIDDEN = "https://api.example.com/errors/forbidden"
    NOT_FOUND = "https://api.example.com/errors/not-found"
    CONFLICT = "https://api.example.com/errors/conflict"
    INTERNAL_SERVER_ERROR = "https://api.example.com/errors/internal-server-error"
    VALIDATION_ERROR = "https://api.example.com/errors/validation-error"
    SERVICE_UNAVAILABLE = "https://api.example.com/errors/service-unavailable"
    PERMISSION_DENIED = "https://api.example.com/errors/permission-denied"
    BUSINESS_ERROR = "https://api.example.com/errors/business-error"

class ProblemDetails(BaseModel):
    """
    RFC 7807 compliant error response structure.
    
    Example:
    {
        "type": "https://api.example.com/errors/not-found",
        "title": "Not Found",
        "status": 404,
        "detail": "Shop with ID 123 does not exist.",
        "instance": "/shops/123"
    }
    """
    model_config = {"arbitrary_types_allowed": True}
    
    type: str = Field(..., description="URI reference that identifies the problem type")
    title: str = Field(..., description="Short, human-readable summary of the problem")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation specific to this occurrence")
    instance: Optional[str] = Field(None, description="URI reference that identifies specific occurrence", exclude=True)

# Authentication response models
class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (e.g., Bearer)")

class UserResponse(BaseModel):
    """User response model."""
    id: int = Field(..., description="User ID")
    username: Optional[str] = Field(None, description="Username")
    email: Optional[str] = Field(None, description="Email address")



# Generic response wrapper for consistent API responses
T = TypeVar('T')


class ApiResponse(BaseModel):
    """
    Standardized success response wrapper.
    
    All successful API responses should use this structure:
    {
        "code": 200,
        "message": "Success",
        "data": {...}
    }
    """
    code: int = Field(..., description="HTTP status code", example=200)
    message: str = Field(..., description="Human-readable status message", example="Success")
    data: Optional[T] = Field(None, description="Response payload data")


class PaginatedResponse(BaseModel):
    """
    Standardized paginated response structure.
    
    Example:
    {
        "code": 200,
        "message": "Success",
        "data": {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 10,
            "total_pages": 10
        }
    }
    """
    code: int = Field(..., description="HTTP status code", example=200)
    message: str = Field(..., description="Human-readable status message", example="Success")
    data: Dict[str, Any] = Field(..., description="Paginated data structure")


class PaginationParams(BaseModel):
    """
    Standardized pagination query parameters.
    
    All list endpoints should accept these parameters:
    - page: Page number (1-based index)
    - page_size: Number of items per page
    """
    page: int = Field(1, ge=1, description="Page number (1-based index)", example=1)
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        description="Number of items per page",
        example=10
    )


# Common response models used across endpoints
class IdResponse(BaseModel):
    """Standard response for create/update operations returning just the ID."""
    id: int = Field(..., description="Resource identifier", example=123)


class CreatedResponse(BaseModel):
    """Standard response for successful resource creation."""
    code: int = 201
    message: str = "Created successfully"
    data: IdResponse


class UpdatedResponse(BaseModel):
    """Standard response for successful resource update."""
    code: int = 200
    message: str = "Updated successfully"
    data: IdResponse


class DeletedResponse(BaseModel):
    """Standard response for successful resource deletion."""
    code: int = 200
    message: str = "Deleted successfully"
    data: Dict[str, Any] = {}


class EmptyResponse(BaseModel):
    """Standard response when no data is returned (e.g., status updates)."""
    code: int = 200
    message: str = "Operation completed successfully"
    data: Optional[Dict[str, Any]] = None


# Domain-specific response models
class ShopResponse(BaseModel):
    """Shop information response."""
    id: int = Field(..., description="Shop ID", example=1)
    name: str = Field(..., description="Shop name", example="Central Store")
    address: Optional[str] = Field(None, description="Shop address", example="123 Main St")
    phone: Optional[str] = Field(None, description="Contact phone", example="+86 1234567890")
    status: int = Field(..., description="Shop status (1=active, 2=inactive)", example=1)
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class PartnerResponse(BaseModel):
    """Partner information response."""
    id: int = Field(..., description="Partner ID", example=1)
    name: str = Field(..., description="Partner name", example="Tech Supplier Co.")
    phone: Optional[str] = Field(None, description="Contact phone", example="+86 1234567890")
    address: Optional[str] = Field(None, description="Partner address")
    type: int = Field(..., description="Partner type (1=supplier, 2=customer)", example=1)
    created_at: datetime = Field(..., description="Creation timestamp")


class StaffResponse(BaseModel):
    """Staff information response."""
    id: int = Field(..., description="Staff ID", example=1)
    username: str = Field(..., description="Username", example="john_doe")
    name: str = Field(..., description="Full name", example="John Doe")
    email: Optional[str] = Field(None, description="Email address", example="john@example.com")
    phone: Optional[str] = Field(None, description="Phone number", example="+86 1234567890")
    role: int = Field(..., description="Role ID (1=owner, 2=manager, 3=staff)", example=3)
    shop_id: Optional[int] = Field(None, description="Associated shop ID", example=1)
    status: int = Field(..., description="Status (1=active, 2=inactive)", example=1)


class DeviceInventoryResponse(BaseModel):
    """Device inventory item response."""
    id: int = Field(..., description="Inventory ID", example=1)
    device_sn: str = Field(..., description="Device serial number", example="SN123456789")
    model: str = Field(..., description="Device model", example="iPhone 15")
    status: int = Field(..., description="Status (1=in stock, 2=sold, 3=repair, 4=scrap)", example=1)
    purchase_price: Optional[float] = Field(None, description="Purchase price", example=599.99)
    selling_price: Optional[float] = Field(None, description="Selling price", example=799.99)
    shop_id: int = Field(..., description="Associated shop ID", example=1)
    created_at: datetime = Field(..., description="Creation timestamp")


class PurchaseOrderResponse(BaseModel):
    """Purchase order response."""
    id: int = Field(..., description="Order ID", example=1)
    partner_id: Optional[int] = Field(None, description="Supplier partner ID", example=1)
    shop_id: int = Field(..., description="Associated shop ID", example=1)
    total_amount: float = Field(..., description="Total order amount", example=5999.99)
    status: int = Field(..., description="Order status (1=pending, 2=completed, 3=cancelled)", example=2)
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class SalesOrderResponse(BaseModel):
    """Sales order response."""
    id: int = Field(..., description="Order ID", example=1)
    customer_name: Optional[str] = Field(None, description="Customer name", example="John Doe")
    shop_id: int = Field(..., description="Associated shop ID", example=1)
    total_amount: float = Field(..., description="Total order amount", example=7999.99)
    status: int = Field(..., description="Order status (1=pending, 2=completed, 3=refunded)", example=2)
    created_at: datetime = Field(..., description="Creation timestamp")


class DictionaryItemResponse(BaseModel):
    """Dictionary item response."""
    id: int = Field(..., description="Dictionary ID", example=1)
    key: str = Field(..., description="Dictionary key", example="device_model")
    value: str = Field(..., description="Dictionary value", example="iPhone 15")
    category: Optional[str] = Field(None, description="Category name", example="smartphone")
    sort_order: int = Field(..., description="Display order", example=1)


# Helper functions for creating standardized responses
def success_response(data: Any, message: str = "Success", code: int = 200) -> ApiResponse:
    """Create a standardized success response."""
    return ApiResponse(code=code, message=message, data=data)


def created_response(id: int, message: str = "Created successfully") -> CreatedResponse:
    """Create a standardized creation response."""
    return CreatedResponse(code=201, message=message, data={"id": id})


def updated_response(id: int, message: str = "Updated successfully") -> UpdatedResponse:
    """Create a standardized update response."""
    return UpdatedResponse(code=200, message=message, data={"id": id})


def deleted_response(message: str = "Deleted successfully") -> DeletedResponse:
    """Create a standardized deletion response."""
    return DeletedResponse(code=200, message=message)


def empty_response(message: str = "Operation completed successfully") -> EmptyResponse:
    """Create a response with no data payload."""
    return EmptyResponse(code=200, message=message)

# RFC 7807 Error Response Helper Functions

def error_response(
    status_code: int,
    detail: str,
    type_url: str = "https://api.example.com/errors/bad-request",
    title: Optional[str] = None,
    instance: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized RFC 7807 compliant error response.
    
    Args:
        status_code: HTTP status code (e.g., 400, 404, 500)
        detail: Human-readable explanation of the error
        type_url: URI reference identifying the problem type
        title: Short human-readable summary (auto-generated if not provided)
        instance: URI reference for specific occurrence
    
    Returns:
        Dictionary with RFC 7807 compliant structure
    """
    # Auto-generate title based on status code if not provided
    if title is None:
        title = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            409: "Conflict",
            422: "Unprocessable Entity",
            500: "Internal Server Error",
            503: "Service Unavailable"
        }.get(status_code, "Error")
    
    response = {
        "type": type_url,
        "title": title,
        "status": status_code,
        "detail": detail
    }
    
    if instance:
        response["instance"] = instance
    
    return response


def bad_request_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 400 Bad Request error."""
    return error_response(
        status_code=400,
        detail=detail,
        type_url="https://api.example.com/errors/bad-request",
        title="Bad Request",
        instance=instance
    )


def unauthorized_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 401 Unauthorized error."""
    return error_response(
        status_code=401,
        detail=detail,
        type_url="https://api.example.com/errors/unauthorized",
        title="Unauthorized",
        instance=instance
    )


def forbidden_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 403 Forbidden error."""
    return error_response(
        status_code=403,
        detail=detail,
        type_url="https://api.example.com/errors/forbidden",
        title="Forbidden",
        instance=instance
    )


def not_found_error(resource_type: str, identifier: str, instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 404 Not Found error."""
    detail = f"{resource_type} with {identifier} does not exist."
    return error_response(
        status_code=404,
        detail=detail,
        type_url="https://api.example.com/errors/not-found",
        title="Not Found",
        instance=instance
    )


def conflict_error(resource_type: str, identifier: str, instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 409 Conflict error."""
    detail = f"{resource_type} with {identifier} already exists."
    return error_response(
        status_code=409,
        detail=detail,
        type_url="https://api.example.com/errors/conflict",
        title="Conflict",
        instance=instance
    )


def internal_error(detail: str = "An unexpected error occurred while processing your request.", instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 500 Internal Server Error."""
    return error_response(
        status_code=500,
        detail=detail,
        type_url="https://api.example.com/errors/internal-server-error",
        title="Internal Server Error",
        instance=instance
    )


def validation_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]:
    """Create a 422 Unprocessable Entity error."""
    return error_response(
        status_code=422,
        detail=detail,
        type_url="https://api.example.com/errors/validation-error",
        title="Unprocessable Entity",
        instance=instance
    )
