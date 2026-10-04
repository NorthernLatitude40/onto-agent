"""
Custom exceptions with RFC 7807 (Problem Details for HTTP APIs) support.

This module provides standardized exception classes that generate RFC 7807 compliant
error responses. All exceptions include:
- type: URI reference identifying the problem type
- title: Human-readable summary
- status: HTTP status code
- detail: Human-readable explanation
- instance: URI of the specific occurrence (optional)
"""

from fastapi import HTTPException, status
from typing import Optional


class ProblemDetails(HTTPException):
    """
    Base class for RFC 7807 compliant exceptions.
    
    All error responses will follow the Problem Details JSON structure:
    {
        "type": "https://api.example.com/errors/{error_type}",
        "title": "Human-readable title",
        "status": 400,
        "detail": "Human-readable explanation",
        "instance": "/path/to/resource" (optional)
    }
    """
    
    def __init__(
        self,
        error_type: str,
        title: str,
        status_code: int,
        detail: str,
        instance: Optional[str] = None,
    ):
        self.error_type = f"https://api.example.com/errors/{error_type}"
        self.title = title
        self.status_code = status_code
        self.detail = detail
        self.instance = instance
        
        headers = {"Content-Type": "application/problem+json"}
        body = {
            "type": self.error_type,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
        }
        if instance:
            body["instance"] = instance
            
        super().__init__(status_code=status_code, detail=body, headers=headers)


class BadRequestError(ProblemDetails):
    """400 Bad Request - Invalid input or parameter."""
    
    def __init__(self, detail: str, instance: Optional[str] = None):
        super().__init__(
            error_type="bad-request",
            title="Bad Request",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            instance=instance,
        )


class UnauthorizedError(ProblemDetails):
    """401 Unauthorized - Authentication required."""
    
    def __init__(self, detail: str = "Authentication credentials are required.", instance: Optional[str] = None):
        super().__init__(
            error_type="unauthorized",
            title="Unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            instance=instance,
        )


class ForbiddenError(ProblemDetails):
    """403 Forbidden - User lacks permission."""
    
    def __init__(self, detail: str = "You do not have permission to access this resource.", instance: Optional[str] = None):
        super().__init__(
            error_type="forbidden",
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            instance=instance,
        )


class NotFoundError(ProblemDetails):
    """404 Not Found - Resource does not exist."""
    
    def __init__(self, resource_type: str, identifier: str, instance: Optional[str] = None):
        detail = f"{resource_type} with {identifier} does not exist."
        super().__init__(
            error_type="not-found",
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            instance=instance,
        )


class ConflictError(ProblemDetails):
    """409 Conflict - Resource already exists."""
    
    def __init__(self, resource_type: str, identifier: str, instance: Optional[str] = None):
        detail = f"{resource_type} with {identifier} already exists."
        super().__init__(
            error_type="conflict",
            title="Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            instance=instance,
        )


class InternalServerError(ProblemDetails):
    """500 Internal Server Error - Unexpected server error."""
    
    def __init__(self, detail: str = "An unexpected error occurred while processing your request.", instance: Optional[str] = None):
        super().__init__(
            error_type="internal-server-error",
            title="Internal Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            instance=instance,
        )


class ValidationError(ProblemDetails):
    """422 Unprocessable Entity - Data validation failed."""
    
    def __init__(self, detail: str = "Data validation failed.", instance: Optional[str] = None):
        super().__init__(
            error_type="validation-error",
            title="Unprocessable Entity",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            instance=instance,
        )


class ServiceUnavailableError(ProblemDetails):
    """503 Service Unavailable - Server temporarily unavailable."""
    
    def __init__(self, detail: str = "Service is currently unavailable. Please try again later.", instance: Optional[str] = None):
        super().__init__(
            error_type="service-unavailable",
            title="Service Unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            instance=instance,
        )


class PermissionDeniedException(ProblemDetails):
    """403 Forbidden - User lacks specific permission."""
    
    def __init__(self, detail: str = "You do not have the required permission to perform this action.", instance: Optional[str] = None):
        super().__init__(
            error_type="permission-denied",
            title="Permission Denied",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            instance=instance,
        )


class BusinessException(ProblemDetails):
    """400 Bad Request - Generic business logic exception."""
    
    def __init__(self, detail: str, instance: Optional[str] = None):
        super().__init__(
            error_type="business-error",
            title="Business Error",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            instance=instance,
        )

# Convenience functions for common errors

def not_found(resource_type: str, identifier: str, instance: Optional[str] = None):
    """Create a 404 Not Found error."""
    return NotFoundError(resource_type, identifier, instance)


def bad_request(detail: str, instance: Optional[str] = None):
    """Create a 400 Bad Request error."""
    return BadRequestError(detail, instance)


def unauthorized(detail: str = "Authentication credentials are required.", instance: Optional[str] = None):
    """Create a 401 Unauthorized error."""
    return UnauthorizedError(detail, instance)


def forbidden(detail: str = "You do not have permission to access this resource.", instance: Optional[str] = None):
    """Create a 403 Forbidden error."""
    return ForbiddenError(detail, instance)


def conflict(resource_type: str, identifier: str, instance: Optional[str] = None):
    """Create a 409 Conflict error."""
    return ConflictError(resource_type, identifier, instance)


def permission_denied(detail: str = "You do not have the required permission to perform this action.", instance: Optional[str] = None):
    """Create a 403 Permission Denied error."""
    return PermissionDeniedException(detail, instance)


def internal_error(detail: str = "An unexpected error occurred while processing your request.", instance: Optional[str] = None):
    """Create a 500 Internal Server Error."""
    return InternalServerError(detail, instance)


def register_exception_handlers(app):
    """
    Register global exception handlers for FastAPI application.
    
    This function sets up handlers for all custom ProblemDetails exceptions,
    ensuring they are properly serialized as RFC 7807 compliant responses.
    
    Args:
        app: FastAPI application instance
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse
    
    @app.exception_handler(ProblemDetails)
    async def problem_details_exception_handler(request: Request, exc: ProblemDetails):
        return JSONResponse(
            content={
                "type": exc.error_type,
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": exc.instance if exc.instance else str(request.url),
            },
            status_code=exc.status_code,
        )
    
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return await problem_details_exception_handler(request, exc)

    # Register handler for standard HTTPException to ensure RFC 7807 compliance
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """
        Convert standard HTTPException to RFC 7807 Problem Details format.
        This ensures all error responses follow the standardized format.
        """
        # Check if the exception already has RFC 7807 format (from our custom exceptions)
        if isinstance(exc.detail, dict) and "type" in exc.detail:
            return JSONResponse(
                content=exc.detail,
                status_code=exc.status_code,
                headers={"Content-Type": "application/problem+json"}
            )
        
        # Convert standard HTTPException to RFC 7807 format
        error_type = "bad-request"
        title = "Bad Request"
        
        # Map status codes to appropriate error types and titles
        status_to_error = {
            400: ("bad-request", "Bad Request"),
            401: ("unauthorized", "Unauthorized"),
            403: ("forbidden", "Forbidden"),
            404: ("not-found", "Not Found"),
            409: ("conflict", "Conflict"),
            422: ("validation-error", "Unprocessable Entity"),
            500: ("internal-server-error", "Internal Server Error"),
            503: ("service-unavailable", "Service Unavailable")
        }
        
        if exc.status_code in status_to_error:
            error_type, title = status_to_error[exc.status_code]
        
        problem_details = {
            "type": f"https://api.example.com/errors/{error_type}",
            "title": title,
            "status": exc.status_code,
            "detail": str(exc.detail) if exc.detail else "An error occurred"
        }
        
        # Add instance URI if not already present
        if "instance" not in problem_details:
            problem_details["instance"] = str(request.url)
        
        return JSONResponse(
            content=problem_details,
            status_code=exc.status_code,
            headers={"Content-Type": "application/problem+json"}
        )
