# RFC 7807 Problem Details for HTTP APIs Implementation

## Overview

This document describes the implementation of [RFC 7807](https://tools.ietf.org/html/rfc7807) (Problem Details for HTTP APIs) across all API endpoints in this codebase.

RFC 7807 defines a standardized way to return error information from APIs, making it easier for clients to handle errors consistently.

## Problem Details Structure

All error responses follow this JSON structure:

```json
{
  "type": "https://api.example.com/errors/{error-type}",
  "title": "Human-readable summary",
  "status": 400,
  "detail": "Human-readable explanation",
  "instance": "/path/to/resource" (optional)
}
```

### Field Descriptions

- **`type`** (required): A URI reference that identifies the problem type. This allows clients to handle different error types appropriately.
- **`title`** (required): A short, human-readable summary of the problem.
- **`status`** (required): The HTTP status code (e.g., 400, 404, 500).
- **`detail`** (required): A human-readable explanation specific to this occurrence of the problem.
- **`instance`** (optional): A URI reference that identifies the specific occurrence of the problem. When dereferenced, it should return more information about this specific occurrence.

## Implementation Details

### 1. Standardized Error Types

All error types are defined in `src/model/response_models.py`:

```python
class ErrorType(str):
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
```

### 2. ProblemDetails Model

The `ProblemDetails` Pydantic model in `src/model/response_models.py` defines the structure:

```python
class ProblemDetails(BaseModel):
    type: ErrorType = Field(..., description="URI reference that identifies the problem type")
    title: str = Field(..., description="Short, human-readable summary of the problem")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation specific to this occurrence")
    instance: Optional[str] = Field(None, description="URI reference that identifies specific occurrence")
```

### 3. Custom Exception Classes

The `src/common/exceptions.py` module provides custom exception classes that automatically generate RFC 7807 compliant responses:

- `BadRequestError`: 400 Bad Request
- `UnauthorizedError`: 401 Unauthorized  
- `ForbiddenError`: 403 Forbidden
- `NotFoundError`: 404 Not Found
- `ConflictError`: 409 Conflict
- `InternalServerError`: 500 Internal Server Error
- `ValidationError`: 422 Unprocessable Entity
- `ServiceUnavailableError`: 503 Service Unavailable
- `PermissionDeniedException`: 403 Permission Denied
- `BusinessException`: 400 Business Logic Error

### 4. Global Exception Handlers

The `register_exception_handlers(app)` function in `src/common/exceptions.py` registers global handlers that ensure all exceptions are properly serialized as RFC 7807 responses.

**Important**: This must be called during application startup:

```python
from src.common.exceptions import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

### 5. Helper Functions for Error Responses

`src/model/response_models.py` provides helper functions to create standardized error responses:

```python
def bad_request_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]
def unauthorized_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]
def forbidden_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]
def not_found_error(resource_type: str, identifier: str, instance: Optional[str] = None) -> Dict[str, Any]
def conflict_error(resource_type: str, identifier: str, instance: Optional[str] = None) -> Dict[str, Any]
def internal_error(detail: str = "An unexpected error occurred while processing your request.", instance: Optional[str] = None) -> Dict[str, Any]
def validation_error(detail: str, instance: Optional[str] = None) -> Dict[str, Any]
```

These functions create properly formatted RFC 7807 responses with appropriate error types and titles.

## Usage Examples

### Example 1: Using Custom Exceptions in API Endpoints

```python
from fastapi import APIRouter
from src.common.exceptions import NotFoundError, BadRequestError

router = APIRouter()

@router.get("/shops/{shop_id}")
async def get_shop(shop_id: int):
    shop = await ShopService.get_by_id(shop_id)
    if not shop:
        raise NotFoundError(resource_type="Shop", identifier=f"ID {shop_id}")
    return shop

@router.post("/shops/")
async def create_shop(shop_data: ShopCreate):
    if not shop_data.name:
        raise BadRequestError(detail="Shop name is required")
    # ... create shop logic
```

### Example 2: Using Helper Functions for Manual Responses

```python
from fastapi import Request, Response
from src.model.response_models import not_found_error

@router.get("/legacy-endpoint")
async def legacy_endpoint(request: Request):
    # Check if resource exists
    if not resource_exists:
        error_response = not_found_error(
            resource_type="Resource",
            identifier="ID 123",
            instance=str(request.url)
        )
        return Response(
            content=json.dumps(error_response),
            status_code=404,
            media_type="application/problem+json"
        )
```

### Example 3: Handling Standard HTTPException

The global exception handler automatically converts standard FastAPI `HTTPException` to RFC 7807 format:

```python
from fastapi import HTTPException

@router.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id < 0:
        raise HTTPException(status_code=400, detail="Item ID must be positive")
    # This will automatically be converted to RFC 7807 format
```

## Testing the Implementation

Run the test script to verify RFC 7807 compliance:

```bash
python test_rfc_7807.py
```

This script tests various error scenarios and validates that all responses conform to the RFC 7807 specification.

## Benefits of RFC 7807 Implementation

1. **Consistency**: All errors follow the same structure across the API
2. **Client-Friendly**: Clients can easily identify and handle different error types
3. **Documentation**: Error types serve as documentation for what went wrong
4. **Extensibility**: New error types can be added without breaking existing clients
5. **Standards Compliance**: Follows IETF standard for HTTP API error responses

## Migration Guide

### For Existing Code Using HTTPException

No changes needed! The global exception handler automatically converts `HTTPException` to RFC 7807 format.

### For New Code

Use the custom exceptions or helper functions:

```python
# Recommended approach
raise NotFoundError(resource_type="Shop", identifier=f"ID {shop_id}")

# Alternative approach
from src.model.response_models import not_found_error
error = not_found_error("Shop", f"ID {shop_id}")
return JSONResponse(content=error, status_code=404)
```

## Error Type Documentation

| Error Type | Status Code | Description |
|------------|-------------|-------------|
| `https://api.example.com/errors/bad-request` | 400 | The server cannot process the request due to client error |
| `https://api.example.com/errors/unauthorized` | 401 | Authentication is required and has failed or not been provided |
| `https://api.example.com/errors/forbidden` | 403 | The request was understood but refused execution |
| `https://api.example.com/errors/not-found` | 404 | The requested resource could not be found |
| `https://api.example.com/errors/conflict` | 409 | Request conflicts with current state of server |
| `https://api.example.com/errors/validation-error` | 422 | The request was well-formed but was unable to be followed due to semantic errors |
| `https://api.example.com/errors/internal-server-error` | 500 | An unexpected condition was encountered |
| `https://api.example.com/errors/service-unavailable` | 503 | The server is not ready to handle the request |
| `https://api.example.com/errors/permission-denied` | 403 | The user does not have permission to access this resource |
| `https://api.example.com/errors/business-error` | 400 | Business logic validation failed |

## Content-Type Header

All error responses include the proper Content-Type header:

```
Content-Type: application/problem+json
```

This allows clients to easily identify RFC 7807 responses.