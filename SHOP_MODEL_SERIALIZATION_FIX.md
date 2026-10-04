# ShopModel Serialization Fix

## Problem

The application was throwing a `PydanticSerializationError` when trying to return `ShopModel` objects from API endpoints:

```
pydantic_core._pydantic_core.PydanticSerializationError: Unable to serialize unknown type: <class 'src.model.shop_model.ShopModel'>
```

## Root Cause

FastAPI/Pydantic doesn't know how to automatically serialize SQLAlchemy model instances by default. When the API tried to return `ShopModel` objects directly, Pydantic couldn't serialize them to JSON.

## Solution

Modified [`src/api/v1/endpoints/shop_api.py`](langgraph_workspace/src/api/v1/endpoints/shop_api.py:78) to convert SQLAlchemy model instances to dictionaries before returning them:

### Changes Made

#### 1. Fixed `create_shop` endpoint (line 78)

**Before:**

```python
return new_shop
```

**After:**

```python
# Convert SQLAlchemy model to dict for JSON serialization
shop_data = {
    "id": new_shop.id,
    "name": new_shop.name,
    "logo": new_shop.logo,
    "contact_name": new_shop.contact_name,
    "contact_phone": new_shop.contact_phone,
    "province": new_shop.province,
    "city": new_shop.city,
    "district": new_shop.district,
    "address_detail": new_shop.address_detail,
    "is_active": new_shop.is_active
}
return success_response(data=shop_data)
```

#### 2. Fixed `get_current_shop_info` endpoint (line 279)

**Before:**

```python
return success_response(data=shop)
```

**After:**

```python
# 将 SQLAlchemy 模型转换为字典以便 JSON 序列化
shop_data = {
    "id": shop.id,
    "name": shop.name,
    "logo": shop.logo,
    "contact_name": shop.contact_name,
    "contact_phone": shop.contact_phone,
    "province": shop.province,
    "city": shop.city,
    "district": shop.district,
    "address_detail": shop.address_detail,
    "is_active": shop.is_active,
    "staff_count": staff_count
}

return success_response(data=shop_data)
```

## Verification

Created a test script [`verify_fix.py`](langgraph_workspace/verify_fix.py) that confirms:

- ✓ ShopModel attributes can be serialized to JSON successfully
- ✓ The serialization logic works correctly for both endpoints
- ✓ JSON round-trip (serialize → deserialize) works as expected

## Impact

This fix resolves the `PydanticSerializationError` and allows the API endpoints to properly return shop data in JSON format.

## Alternative Approaches Considered

1. **Using Pydantic's `model_dump()`**: Could use `ShopResponse.model_validate(shop).model_dump()` but requires proper Pydantic model setup
2. **SQLAlchemy session configuration**: Could configure SQLAlchemy to return dictionaries, but this would affect all queries
3. **Custom JSON encoder**: Could create a custom JSON encoder for SQLAlchemy models, but more complex

The chosen approach (manual dict conversion) is:

- Simple and explicit
- Easy to understand and maintain
- Minimal impact on existing code
- Works with the existing `success_response` pattern
