# API Consistency Report

## Executive Summary

The frontend and backend APIs have **32 inconsistencies**:

- **22 frontend API calls** without corresponding backend endpoints
- **10 backend endpoints** not used by the frontend
- **0 matching endpoints** between frontend and backend

## Detailed Findings

### 🔴 Frontend Calls Without Backend Endpoints (22)

These endpoints are called by the frontend but don't exist in the backend:

```
/api/v1/auth/me
/api/v1/auth/wx-login
/api/v1/dashboard/overview
/api/v1/dicts
/api/v1/dicts/device-models
/api/v1/dicts/device-models/brands
/api/v1/inventories/create
/api/v1/inventories/device/add
/api/v1/inventories/device/add-detailed
/api/v1/inventories/device/options
/api/v1/inventories/device/sell
/api/v1/inventories/list
/api/v1/inventories/list?status=1
/api/v1/inventories/search_by_sn
/api/v1/purchases/list
/api/v1/shop/chat
/api/v1/shop/staffs
/api/v1/shop/staffs/accept-invite
/api/v1/shop/staffs/create
/api/v1/shops/current
/api/v1/shops/my-shops
/api/v1/user/default-identity
```

### ⚠️ Backend Endpoints Not Used by Frontend (10)

These backend endpoints exist but are never called by the frontend:

```
POST /api/v1/create
GET  /api/v1/detail/{order_id}
POST /api/v1/device/add
POST /api/v1/device/add-detailed
GET  /api/v1/device/options
GET  /api/v1/inventory/detail/{target_id}
GET  /api/v1/list
POST /api/v1/refund
GET  /api/v1/search_by_sn
POST /api/v1/status
```

## Root Cause Analysis

### Path Structure Mismatch

The frontend uses a **resource-based path structure** (e.g., `/api/v1/inventories/list`) while the backend uses a **simpler structure** (e.g., `/api/v1/list`). This inconsistency causes most of the mismatches.

### Missing Backend Endpoints

The backend is missing many endpoints that the frontend expects:

- Authentication endpoints (`/auth/me`, `/auth/wx-login`)
- Dashboard endpoints (`/dashboard/overview`)
- Dictionary endpoints (`/dicts`, `/dicts/device-models`)
- Inventory management endpoints (`/inventories/create`, `/inventories/list`)
- Shop and staff management endpoints
- User identity endpoints

### Unused Backend Endpoints

The backend has endpoints that don't seem to be used by the current frontend:

- Order-related endpoints (`/create`, `/detail/{order_id}`, `/refund`, `/status`)
- Device management endpoints (`/device/add`, `/device/add-detailed`, `/device/options`)

## Recommendations

### Immediate Actions (High Priority)

1. **Add missing backend endpoints** to match frontend expectations
2. **Update frontend paths** to match existing backend structure, OR
3. **Refactor both sides** to use a consistent path structure

### Long-term Solutions

1. **Implement API versioning** to ensure backward compatibility
2. **Create OpenAPI/Swagger documentation** for both frontend and backend
3. **Set up automated consistency checks** in CI/CD pipeline
4. **Establish API design guidelines** for path structure and naming conventions

## Technical Details

### Backend Analysis

- **File analyzed**: `./langgraph_workspace/src/api/v1/endpoints/inventory_api.py`
- **Total endpoints found**: 10
- **HTTP methods**: POST (6), GET (4)

### Frontend Analysis

- **Directory analyzed**: `./miniprogram-1/miniprogram`
- **Files scanned**: All `.ts` files
- **Total API calls found**: 33
- **Default method assumed**: GET (for all frontend calls)

## Script Used for Analysis

A Python script was created to automatically detect these inconsistencies:

```python
./langgraph_workspace/api_consistency_check.py
```

This script can be run periodically to ensure API consistency is maintained.

---

**Report Generated**: 2026-10-02
**Analysis Tool**: api_consistency_check.py
**Status**: ❌ Inconsistent (32 issues found)
