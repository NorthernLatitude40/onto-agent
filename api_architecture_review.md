# API Architecture Review

## Executive Summary

The current API architecture follows a modular, FastAPI-based RESTful design with versioned endpoints (`/api/v1`). The codebase demonstrates good separation of concerns through dedicated endpoint files and central routing. However, there are several areas for improvement in consistency, error handling, documentation, and maintainability.

---

## Strengths

### 1. Modular Organization ✓
- Endpoints are well-separated into domain-specific files (e.g., `shop_api.py`, `partner_api.py`, `inventory_api.py`)
- Central router (`router.py`) aggregates all v1 endpoints cleanly
- Clear prefix-based routing structure

### 2. FastAPI Best Practices ✓
- Proper use of response models for type safety and documentation
- Dependency injection with `Depends()` for database sessions
- HTTP status codes are appropriately set (e.g., `201_CREATED`)
- Summary descriptions provide good API documentation

### 3. Internationalization Support ✓
- Endpoints support multiple languages through headers (`Accept-Language`)
- Error messages are localized where implemented

---

## Areas for Improvement

### 1. Inconsistent Endpoint Naming 🔄

**Current State:**
```python
# shop_api.py - POST /create
@router.post("/create", ...)
def create_shop(...):

# partner_api.py - POST "" (empty path)
@router.post("", ...)
async def create_partner(...):
```

**Issues:**
- Some endpoints use explicit names like `/create`, others use empty strings for the base route
- Inconsistent naming between similar operations across domains
- Missing resource identifiers in some routes (e.g., should be `/shops` not just `/create`)

**Recommendation:**
Standardize on RESTful conventions:
- Collection endpoints: `GET /shops`, `POST /shops`
- Individual items: `GET /shops/{shop_id}`, `PUT /shops/{shop_id}`, `DELETE /shops/{shop_id}`
- Actions: `POST /shops/{shop_id}/activate` (not `/update`)

### 2. Error Handling Centralization ⚠️

**Current State:**
```python
try:
    # business logic
    if error_condition:
        raise HTTPException(status_code=400, detail="Error message")
except Exception as e:
    logger.error(f"Error: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

**Issues:**
- Error handling is duplicated across endpoints
- Inconsistent error messages and status codes
- Some endpoints use generic `HTTPException` without proper categorization
- No centralized exception handling middleware

**Recommendation:**
1. Create custom exception classes in `src/common/exceptions.py`:
   ```python
   class ValidationError(Exception): ...
   class ResourceNotFound(Exception): ...
   class PermissionDenied(Exception): ...
   ```

2. Add FastAPI exception handlers in main router:
   ```python
   @app.exception_handler(ValidationError)
   async def validation_exception_handler(request, exc):
       return JSONResponse(...)
   ```

3. Use RFC 7807 (Problem Details) for error responses where appropriate

### 3. Response Model Inconsistencies 📋

**Current State:**
- Some endpoints use `ApiResponse` wrapper
- Others return domain-specific models directly
- Inconsistent pagination implementations

**Recommendation:**
1. Standardize on response structure:
   ```python
   {
     "success": boolean,
     "data": any,
     "message": string,
     "code": string (optional)
   }
   ```

2. Create pagination model:
   ```python
   class PaginatedResponse(BaseModel):
       items: List[Any]
       total: int
       page: int
       size: int
   ```

3. Apply consistently across all list endpoints

### 4. Missing Pagination 📄

**Current State:**
- Several list endpoints don't implement pagination
- Examples: `get_inventory_list`, `get_order_list`
- Risk of performance issues with large datasets

**Recommendation:**
1. Add pagination parameters to all list endpoints:
   ```python
   @router.get("/list")
   def get_list(page: int = 1, size: int = 20):
       # implementation
   ```

2. Default page size should be configurable (e.g., 20-50 items)
3. Maximum page size limit to prevent abuse

### 5. Documentation Standards 📚

**Current State:**
- Some endpoints have good summaries
- Others lack detailed descriptions
- No examples in OpenAPI docs
- Missing parameter descriptions

**Recommendation:**
1. Enhance endpoint documentation:
   ```python
   @router.post("/shops", 
                response_model=ShopResponse,
                status_code=status.HTTP_201_CREATED,
                summary="Create a new shop",
                description="Creates a new retail shop with the provided information.",
                responses={
                    201: {"description": "Shop created successfully"},
                    400: {"description": "Invalid input data"},
                    409: {"description": "Shop already exists"}
                })
   ```

2. Add examples using FastAPI's `examples` parameter
3. Document security requirements (e.g., required roles)

### 6. Security Considerations 🔒

**Current State:**
- Some endpoints check permissions manually
- Inconsistent permission validation
- No rate limiting implemented

**Recommendation:**
1. Create permission decorator:
   ```python
   def requires_permission(permission: str):
       def decorator(func):
           @wraps(func)
           async def wrapper(*args, **kwargs):
               current_user = kwargs.get('current_user')
               if not has_permission(current_user, permission):
                   raise PermissionDenied()
               return await func(*args, **kwargs)
           return wrapper
       return decorator
   ```

2. Apply consistently across all endpoints
3. Add rate limiting middleware for public endpoints
4. Validate shop_id ownership where applicable

### 7. Code Organization 📁

**Current State:**
- Some endpoint files are very large (e.g., `inventory_api.py` with 1203 lines)
- Mixed concerns in some files

**Recommendation:**
1. Split large files into smaller, focused modules:
   - `inventory_api.py` → `purchase_api.py`, `sales_api.py`, `device_api.py`
   - Keep related operations together

2. Move complex business logic to service layer:
   ```python
   # inventory_service.py
   class InventoryService:
       def get_inventory_list(shop_id, ...): ...
   
   # inventory_api.py
   @router.get("/list")
   def get_list(current_user, inventory_service: InventoryService = Depends()):
       return inventory_service.get_inventory_list(current_user.shop_id)
   ```

---

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 weeks)
1. ✅ Standardize endpoint naming conventions
2. ✅ Create custom exception classes
3. ✅ Add centralized error handling middleware
4. ✅ Implement pagination on list endpoints
5. ✅ Enhance OpenAPI documentation

### Phase 2: Structural Improvements (2-3 weeks)
1. Split large endpoint files into smaller modules
2. Create service layer for business logic
3. Standardize response models across all endpoints
4. Add permission validation decorators
5. Implement rate limiting

### Phase 3: Advanced Features (ongoing)
1. Add API versioning strategy for future versions
2. Implement request/response logging middleware
3. Add health check and metrics endpoints
4. Document migration path for breaking changes

---

## Specific Recommendations by File

### `shop_api.py`
- **Issue:** Mixed route styles (`/create`, `/update`, `/{target_shop_id}`)
- **Fix:** Standardize to RESTful conventions:
  - `POST /shops` (not `/create`)
  - `PUT /shops/{shop_id}` (not `/update`)
  - `DELETE /shops/{shop_id}`

### `partner_api.py`
- **Issue:** Empty path string for base route
- **Fix:** Use explicit resource name: `POST /partners`

### `inventory_api.py`
- **Issue:** File is too large (1203 lines)
- **Fix:** Split into:
  - `device_api.py` - device management
  - `sales_api.py` - sales operations
  - `purchase_api.py` - purchase operations
  - `status_api.py` - status updates

---

## Conclusion

The current API architecture is functionally sound but needs standardization and refactoring to improve maintainability, consistency, and developer experience. The recommended changes follow FastAPI best practices and RESTful conventions while addressing the specific issues identified in the codebase.

**Estimated effort:** 4-6 weeks for complete implementation
**Priority:** High - inconsistencies will increase technical debt over time