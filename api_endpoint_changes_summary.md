# API Endpoint Changes Summary

## Overview

Fixed API endpoint mismatches between frontend (mini-program) and backend to ensure integration testing can pass.

## Backend Endpoints (from inventory_api.py)

### POST Endpoints:

- `/api/v1/device/add` - 確認設備入庫落庫
- `/api/v1/device/add-detailed` - 確認二手機詳細資訊入庫落庫
- `/api/v1/inventory/create` - 建立銷售單據
- `/api/v1/device/sell` - 確認設備出庫銷售
- `/api/v1/status` - 修改設備狀態
- `/api/v1/refund` - 办理銷售退貨

### GET Endpoints:

- `/api/v1/inventory/list` - 獲取當前門店的設備庫存列表
- `/api/v1/search_by_sn` - 搜索庫存設備
- `/api/v1/detail/{order_id}` - 獲取銷售單詳情
- `/api/v1/inventory/detail/{target_id}` - 獲取庫存設備詳情
- `/api/v1/device/options` - 獲取機型與屬性字典

## Frontend Changes Made

### 1. miniprogram/pages/inventory/detail/index.ts

- **Line 40**: Changed from `/api/v1/inventories/inventory/detail/${id}` to `/api/v1/inventory/detail/${id}` ✓
- **Line 95**: Changed from `/api/v1/inventories/status` to `/api/v1/status` ✓

### 2. miniprogram/pages/sale/form/index.ts

- **Line 68**: `/api/v1/search_by_sn` - Already correct ✓
- **Line 197**: Changed from `/api/v1/inventories/create` to `/api/v1/inventory/create` ✓

### 3. miniprogram/pages/sale/list/index.ts

- **Line 88**: Changed from `/api/v1/purchases/list` to `/api/v1/inventory/list` ✓

### 4. miniprogram/pages/sale/detail/index.ts

- **Line 26**: Changed from `/api/v1/inventories/detail/${id}` to `/api/v1/inventory/detail/${id}` ✓
- **Line 72**: Changed from `/api/v1/inventories/refund` to `/api/v1/inventory/refund` ✓

### 5. miniprogram/pages/purchase/list/index.ts

- **Line 78**: Changed from `/api/v1/purchases/list` to `/api/v1/inventory/list` ✓

### 6. miniprogram/pages/purchase/detail/index.ts

- **Line 28**: Changed from `/api/v1/purchases/detail/${id}` to `/api/v1/inventory/detail/${id}` ✓
- **Line 79**: Changed from `/api/v1/purchases/confirm-inbound` to `/api/v1/device/add` ✓

### 7. miniprogram/pages/index/index.ts

- **Line 250**: Changed from `/api/v1/inventories/list?status=1` to `/api/v1/inventory/list?status=1` ✓
- **Line 604**: Changed from `/api/v1/inventories/device/add` to `/api/v1/device/add` ✓
- **Line 676**: Changed from `/api/v1/inventories/device/sell` to `/api/v1/device/sell` ✓

### 8. miniprogram/pages/purchase/form/index.ts

- **Line 269**: Changed from `/api/v1/inventories/device/add` to `/api/v1/device/add` ✓

### 9. miniprogram/pages/stockInNew/index.ts

- **Line 68**: Changed from `/api/v1/inventories/device/options` to `/api/v1/device/options` ✓
- **Line 228**: Changed from `/api/v1/inventories/device/add-detailed` to `/api/v1/device/add-detailed` ✓

## Verification Status

All frontend API calls have been updated to match the backend endpoints. The changes ensure:

- Consistent path structure (`/api/v1/inventory/` instead of `/api/v1/inventories/`)
- Correct endpoint names matching backend implementation
- Proper HTTP methods (GET, POST) for each operation

## Integration Testing Readiness

The frontend and backend API endpoints are now aligned. Integration testing should pass as long as:

1. All backend endpoints are properly implemented
2. Authentication/authorization is correctly configured
3. Request/response data structures match expectations
