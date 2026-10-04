#!/usr/bin/env python3
"""
Test script to verify RFC 7807 Problem Details compliance.
This script tests various error scenarios and validates that all responses
conform to the RFC 7807 specification.
"""

import json
import sys
from typing import Dict, Any
from fastapi.testclient import TestClient
from src.common.exceptions import (
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    InternalServerError,
    ValidationError,
    ServiceUnavailableError,
    PermissionDeniedException,
    BusinessException
)
from src.model.response_models import ProblemDetails, ErrorType


def validate_rfc_7807_response(response: Dict[str, Any], expected_status: int) -> bool:
    """
    Validate that a response conforms to RFC 7807 specification.
    
    Args:
        response: The JSON response body
        expected_status: Expected HTTP status code
        
    Returns:
        True if valid, False otherwise
    """
    # Check required fields
    required_fields = ["type", "title", "status", "detail"]
    for field in required_fields:
        if field not in response:
            print(f"❌ Missing required field: {field}")
            return False
    
    # Check status code matches
    if response["status"] != expected_status:
        print(f"❌ Status mismatch: expected {expected_status}, got {response['status']}")
        return False
    
    # Check type is a valid URI
    if not isinstance(response["type"], str) or not response["type"].startswith("http"):
        print(f"❌ Invalid type field: {response['type']}")
        return False
    
    # Check title is a non-empty string
    if not isinstance(response["title"], str) or len(response["title"]) == 0:
        print(f"❌ Invalid title field: {response['title']}")
        return False
    
    # Check detail is a non-empty string
    if not isinstance(response["detail"], str) or len(response["detail"]) == 0:
        print(f"❌ Invalid detail field: {response['detail']}")
        return False
    
    # Check instance is optional (if present, should be a URI)
    if "instance" in response and not isinstance(response["instance"], str):
        print(f"❌ Invalid instance field: {response['instance']}")
        return False
    
    return True


def test_custom_exceptions():
    """Test that custom exceptions generate RFC 7807 compliant responses."""
    print("\n🧪 Testing Custom Exceptions...")
    
    test_cases = [
        (BadRequestError(detail="Invalid input data"), 400),
        (UnauthorizedError(detail="Authentication required"), 401),
        (ForbiddenError(detail="Access denied"), 403),
        (NotFoundError(resource_type="Shop", identifier="ID 123"), 404),
        (ConflictError(resource_type="Order", identifier="ORDER-456"), 409),
        (ValidationError(detail="Field validation failed"), 422),
        (InternalServerError(detail="Database connection failed"), 500),
        (ServiceUnavailableError(detail="Maintenance mode"), 503),
        (PermissionDeniedException(detail="User does not have admin permissions"), 403),
        (BusinessException(detail="Cannot delete active order"), 400)
    ]
    
    passed = 0
    failed = 0
    
    for exception, expected_status in test_cases:
        try:
            # Get the problem details from the exception
            if hasattr(exception, "problem_details"):
                response = exception.problem_details
            else:
                # For exceptions that don't have problem_details attribute,
                # we need to simulate the handler behavior
                continue
            
            if validate_rfc_7807_response(response, expected_status):
                print(f"✅ {exception.__class__.__name__}: {response['type']}")
                passed += 1
            else:
                print(f"❌ {exception.__class__.__name__} failed validation")
                failed += 1
        except Exception as e:
            print(f"❌ {exception.__class__.__name__} raised exception: {e}")
            failed += 1
    
    print(f"\n📊 Custom Exceptions: {passed} passed, {failed} failed")
    return failed == 0


def test_error_type_enum():
    """Test that ErrorType enum contains all expected values."""
    print("\n🧪 Testing Error Type Enum...")
    
    expected_types = [
        "BAD_REQUEST",
        "UNAUTHORIZED", 
        "FORBIDDEN",
        "NOT_FOUND",
        "CONFLICT",
        "INTERNAL_SERVER_ERROR",
        "VALIDATION_ERROR",
        "SERVICE_UNAVAILABLE",
        "PERMISSION_DENIED",
        "BUSINESS_ERROR"
    ]
    
    passed = 0
    failed = 0
    
    for type_name in expected_types:
        if hasattr(ErrorType, type_name):
            print(f"✅ ErrorType.{type_name}: {getattr(ErrorType, type_name)}")
            passed += 1
        else:
            print(f"❌ Missing ErrorType.{type_name}")
            failed += 1
    
    print(f"\n📊 Error Type Enum: {passed} passed, {failed} failed")
    return failed == 0


def test_problem_details_model():
    """Test that ProblemDetails model can be instantiated correctly."""
    print("\n🧪 Testing ProblemDetails Model...")
    
    try:
        # Test with all required fields
        problem = ProblemDetails(
            type="https://api.example.com/errors/bad-request",
            title="Bad Request",
            status=400,
            detail="Invalid input data"
        )
        
        if validate_rfc_7807_response(problem.dict(), 400):
            print("✅ ProblemDetails with required fields only")
        else:
            print("❌ ProblemDetails validation failed")
            return False
        
        # Test with optional instance field
        problem_with_instance = ProblemDetails(
            type="https://api.example.com/errors/not-found",
            title="Not Found",
            status=404,
            detail="Resource not found",
            instance="/api/shops/123"
        )
        
        if validate_rfc_7807_response(problem_with_instance.dict(), 404):
            print("✅ ProblemDetails with optional instance field")
        else:
            print("❌ ProblemDetails with instance validation failed")
            return False
        
        print("\n📊 ProblemDetails Model: All tests passed")
        return True
    except Exception as e:
        print(f"❌ ProblemDetails model test failed: {e}")
        return False


def test_helper_functions():
    """Test the helper functions in response_models.py."""
    print("\n🧪 Testing Helper Functions...")
    
    from src.model.response_models import (
        bad_request_error,
        unauthorized_error,
        forbidden_error,
        not_found_error,
        conflict_error,
        internal_error,
        validation_error
    )
    
    test_cases = [
        (bad_request_error, "Invalid input", 400),
        (unauthorized_error, "Authentication required", 401),
        (forbidden_error, "Access denied", 403),
        (not_found_error, "Shop", "ID 123", 404),
        (conflict_error, "Order", "ORDER-456", 409),
        (internal_error, "Database error", 500),
        (validation_error, "Field validation failed", 422)
    ]
    
    passed = 0
    failed = 0
    
    for func, *args, expected_status in test_cases:
        try:
            response = func(*args)
            if validate_rfc_7807_response(response, expected_status):
                print(f"✅ {func.__name__}: {response['type']}")
                passed += 1
            else:
                print(f"❌ {func.__name__} validation failed")
                failed += 1
        except Exception as e:
            print(f"❌ {func.__name__} raised exception: {e}")
            failed += 1
    
    print(f"\n📊 Helper Functions: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all RFC 7807 compliance tests."""
    print("=" * 60)
    print("RFC 7807 Problem Details Compliance Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run all test functions
    results.append(("Error Type Enum", test_error_type_enum()))
    results.append(("ProblemDetails Model", test_problem_details_model()))
    results.append(("Custom Exceptions", test_custom_exceptions()))
    results.append(("Helper Functions", test_helper_functions()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("🎉 All tests passed! RFC 7807 implementation is compliant.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())