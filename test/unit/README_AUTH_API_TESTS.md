# Auth API Unit Tests - Summary

## Overview
This directory contains comprehensive unit tests for the authentication API (`src/api/auth_api.py`).

## Test Coverage

### test_auth_api_simple.py
A complete set of 26 unit tests covering all authentication functionality:

1. **TestCreateAccessToken** (2 tests)
   - Tests JWT token creation with standard and extra data

2. **TestGetCurrentUser** (4 tests)
   - Successful user retrieval from JWT token
   - Invalid token handling
   - Missing sub claim handling
   - User not found in database

3. **TestGetCurrentStaff** (5 tests)
   - Successful staff retrieval with shop ID
   - Missing shop ID handling
   - Staff not found
   - Disabled staff account
   - Pending activation staff

4. **TestAllowShopManager** (2 tests)
   - Permission check for shop managers
   - Forbidden access for non-managers

5. **TestWxLogin** (5 tests)
   - Successful login for new users
   - Empty code validation
   - Weixin API error handling
   - Missing openid in response
   - Successful login for existing users

6. **TestGetMyInfo** (3 tests)
   - Successful info retrieval
   - Staff profile not found
   - Inactive staff handling

7. **TestUpdateMyInfo** (3 tests)
   - Successful info update
   - No fields provided validation
   - Invalid default shop validation

8. **TestPermissionChecker** (2 tests)
   - Permission check for allowed users
   - Forbidden access for unauthorized users

## Key Features Tested

- JWT token generation and validation
- WeChat mini-program authentication flow
- SQLAlchemy database operations
- Role-based access control (RBAC)
- FastAPI dependency injection patterns
- Error handling and edge cases

## Running Tests

```bash
# Run all auth API tests
pytest test/unit/test_auth_api_simple.py -v

# Run specific test class
pytest test/unit/test_auth_api_simple.py::TestWxLogin -v

# Run specific test method
pytest test/unit/test_auth_api_simple.py::TestCreateAccessToken::test_create_access_token_success -v
```

## Test Results
All 26 tests pass successfully with comprehensive coverage of authentication scenarios.
