"""
Unit tests for dict_api.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Import the API module and schemas
from src.api.v1.endpoints.dict_api import (
    get_dictionaries,
    create_dictionary,
    delete_dictionary,
    get_device_models,
    create_device_model,
    delete_device_model,
    get_brands,
    create_model_attribute,
    get_model_attributes,
    delete_attribute,
    ModelCreate
)
from src.model.device_models import DeviceModel, DeviceModelAttribute
from src.model.dict_schema import DictCreate, AttributeCreate


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def mock_async_db_session():
    """Create a mock async database session"""
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # Create a basic mock with query method (without spec to avoid issues)
    db = MagicMock()
    db.query.return_value = db  # Allow chaining
    
    # Mock async methods that return awaitable objects
    async_result = MagicMock()
    async_result.scalar.return_value = None
    
    async def mock_execute(*args, **kwargs):
        return async_result
    
    async def mock_scalars(*args, **kwargs):
        return async_result
    
    db.execute = mock_execute
    db.scalars = mock_scalars
    
    return db


# Test fixtures for test data
@pytest.fixture
def sample_dict_items():
    """Sample dictionary items for testing"""
    items = [
        DeviceModelAttribute(
            id=1,
            model_id=None,
            attr_type="condition",
            attr_value="新品",
            sort_order=1
        ),
        DeviceModelAttribute(
            id=2,
            model_id=None,
            attr_type="condition",
            attr_value="全新",
            sort_order=2
        ),
        DeviceModelAttribute(
            id=3,
            model_id=None,
            attr_type="network",
            attr_value="移動",
            sort_order=1
        )
    ]
    return items


@pytest.fixture
def sample_device_models():
    """Sample device models for testing"""
    models = [
        DeviceModel(
            id=1,
            brand="Apple",
            model_name="iPhone 13",
            is_active=True,
            sort_order=1
        ),
        DeviceModel(
            id=2,
            brand="Apple",
            model_name="iPhone 14",
            is_active=True,
            sort_order=2
        ),
        DeviceModel(
            id=3,
            brand="Huawei",
            model_name="P50 Pro",
            is_active=False,
            sort_order=3
        )
    ]
    return models


@pytest.fixture
def sample_model_attributes():
    """Sample model attributes for testing"""
    attrs = [
        DeviceModelAttribute(
            id=10,
            model_id=1,
            attr_type="storage",
            attr_value="128GB",
            sort_order=1
        ),
        DeviceModelAttribute(
            id=11,
            model_id=1,
            attr_type="color",
            attr_value="星光色",
            sort_order=2
        ),
        DeviceModelAttribute(
            id=12,
            model_id=2,
            attr_type="storage",
            attr_value="256GB",
            sort_order=1
        )
    ]
    return attrs


# ==================== Test Dictionary Endpoints ====================

def test_get_dictionaries_success(mock_db_session, sample_dict_items):
    """Test successful retrieval of dictionary items"""
    # Setup mock - filter by attr_type="condition"
    condition_items = [item for item in sample_dict_items if item.attr_type == "condition"]
    mock_db_session.query().filter().order_by().all.return_value = condition_items
    
    # Call the endpoint
    result = get_dictionaries(attr_type="condition", db=mock_db_session)
    
    # Assertions
    assert len(result) == 2  # Only condition type items
    assert result[0].id == 1
    assert result[0].attr_value == "新品"
    assert result[1].id == 2
    assert result[1].attr_value == "全新"


def test_get_dictionaries_empty(mock_db_session):
    """Test retrieval when no items exist"""
    # Setup mock to return empty list
    mock_db_session.query().filter().order_by().all.return_value = []
    
    # Call the endpoint
    result = get_dictionaries(attr_type="network", db=mock_db_session)
    
    # Assertions
    assert len(result) == 0


def test_create_dictionary_success(mock_db_session):
    """Test successful creation of dictionary item"""
    # Setup mock
    new_item = DeviceModelAttribute(
        id=1,
        model_id=None,
        attr_type="condition",
        attr_value="全新",
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = None  # No existing item
    mock_db_session.add.return_value = None
    mock_db_session.commit.return_value = None
    
    # Mock the refresh to return the object with proper ID
    new_item_with_id = DeviceModelAttribute(
        id=1,
        model_id=None,
        attr_type="condition",
        attr_value="全新",
        sort_order=0
    )
    mock_db_session.refresh.return_value = None  # refresh doesn't return anything, object is modified in place
    
    # Call the endpoint
    payload = DictCreate(attr_type="condition", attr_value="全新", sort_order=0)
    result = create_dictionary(item=payload, db=mock_db_session)
    
    # Assertions
    assert result.attr_type == "condition"
    assert result.attr_value == "全新"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_create_dictionary_duplicate_fails(mock_db_session):
    """Test that creating duplicate dictionary item fails"""
    from fastapi import HTTPException
    
    # Setup mock - item already exists
    existing_item = DeviceModelAttribute(
        id=1,
        model_id=None,
        attr_type="condition",
        attr_value="新品",
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = existing_item
    
    # Call the endpoint
    payload = DictCreate(attr_type="condition", attr_value="新品", sort_order=0)
    
    # Should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_dictionary(item=payload, db=mock_db_session)
    
    assert exc_info.value.status_code == 400
    assert "已存在" in str(exc_info.value.detail)


def test_delete_dictionary_success(mock_db_session):
    """Test successful deletion of dictionary item"""
    # Setup mock
    target = DeviceModelAttribute(
        id=1,
        model_id=None,
        attr_type="condition",
        attr_value="新品",
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = target
    mock_db_session.delete.return_value = None
    mock_db_session.commit.return_value = None
    
    # Call the endpoint
    result = delete_dictionary(attr_id=1, db=mock_db_session)
    
    # Assertions
    assert result["message"] == "刪除成功"
    mock_db_session.delete.assert_called_once_with(target)
    mock_db_session.commit.assert_called_once()


def test_delete_dictionary_not_found(mock_db_session):
    """Test deletion of non-existent dictionary item"""
    from fastapi import HTTPException
    
    # Setup mock - no item found
    mock_db_session.query().filter().first.return_value = None
    
    # Call the endpoint
    with pytest.raises(HTTPException) as exc_info:
        delete_dictionary(attr_id=999, db=mock_db_session)
    
    assert exc_info.value.status_code == 404
    assert "不存在" in str(exc_info.value.detail)


def test_delete_dictionary_not_general(mock_db_session):
    """Test deletion of non-general dictionary item (model_id is not None)"""
    from fastapi import HTTPException
    
    # Setup mock - no item found because model_id filter excludes it
    mock_db_session.query().filter().first.return_value = None
    
    # Call the endpoint - should fail with 404 because item not found
    with pytest.raises(HTTPException) as exc_info:
        delete_dictionary(attr_id=1, db=mock_db_session)
    
    assert exc_info.value.status_code == 404


# ==================== Test Device Model Endpoints ====================

def test_get_device_models_all(mock_db_session, sample_device_models):
    """Test retrieval of all device models"""
    # Setup mock
    mock_db_session.query().order_by().all.return_value = sample_device_models
    
    # Call the endpoint
    result = get_device_models(brand=None, db=mock_db_session)
    
    # Assertions
    assert len(result) == 3
    assert result[0].id == 1
    assert result[1].id == 2
    assert result[2].id == 3


def test_get_device_models_by_brand(mock_db_session, sample_device_models):
    """Test retrieval of device models by brand"""
    # Setup mock - filter by Apple brand
    apple_models = [sample_device_models[0], sample_device_models[1]]
    mock_db_session.query().filter().order_by().all.return_value = apple_models
    
    # Call the endpoint
    result = get_device_models(brand="Apple", db=mock_db_session)
    
    # Assertions
    assert len(result) == 2
    assert all(m.brand == "Apple" for m in result)


def test_get_device_models_empty(mock_db_session):
    """Test retrieval when no models exist"""
    # Setup mock to return empty list
    mock_db_session.query().order_by().all.return_value = []
    
    # Call the endpoint
    result = get_device_models(brand="Samsung", db=mock_db_session)
    
    # Assertions
    assert len(result) == 0


def test_create_device_model_success(mock_db_session):
    """Test successful creation of device model"""
    # Setup mock
    created_model = DeviceModel(
        id=1,
        brand="Apple",
        model_name="iPhone 15",
        is_active=True,
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = None  # No existing model
    mock_db_session.add.return_value = None
    mock_db_session.commit.return_value = None
    
    # Mock the refresh to set the ID on the created object
    def mock_refresh(obj):
        obj.id = 1
        return None
    
    mock_db_session.refresh = mock_refresh
    
    # Call the endpoint
    payload = ModelCreate(brand="Apple", model_name="iPhone 15", sort_order=0)
    result = create_device_model(item=payload, db=mock_db_session)


def test_create_device_model_duplicate(mock_db_session):
    """Test creation of duplicate device model fails with HTTPException"""
    # Setup mock - existing model found
    existing_model = DeviceModel(
        id=1,
        brand="Apple",
        model_name="iPhone 15",
        is_active=True,
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = existing_model
    
    # Call the endpoint
    payload = ModelCreate(brand="Apple", model_name="iPhone 15", sort_order=0)
    
    # Should raise HTTPException with status code 400
    with pytest.raises(HTTPException) as exc_info:
        create_device_model(item=payload, db=mock_db_session)
    
    assert exc_info.value.status_code == 400
    assert "已存在此機型名稱" in exc_info.value.detail
    


def test_create_device_model_duplicate_fails(mock_db_session):
    """Test that creating duplicate device model fails"""
    from fastapi import HTTPException
    
    # Setup mock - model already exists
    existing_model = DeviceModel(
        id=1,
        brand="Apple",
        model_name="iPhone 13",
        is_active=True,
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = existing_model
    
    # Call the endpoint
    payload = ModelCreate(brand="Apple", model_name="iPhone 13", sort_order=0)
    
    # Should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_device_model(item=payload, db=mock_db_session)
    
    assert exc_info.value.status_code == 400
    assert "已存在此機型" in str(exc_info.value.detail)


def test_delete_device_model_success(mock_db_session):
    """Test successful deletion of device model"""
    # Setup mock
    target = DeviceModel(
        id=1,
        brand="Apple",
        model_name="iPhone 13",
        is_active=True,
        sort_order=0
    )
    
    mock_db_session.query().filter().first.return_value = target
    mock_db_session.delete.return_value = None
    mock_db_session.commit.return_value = None
    
    # Call the endpoint
    result = delete_device_model(model_id=1, db=mock_db_session)
    
    # Assertions
    assert result["message"] == "機型已成功刪除"
    mock_db_session.delete.assert_called_once_with(target)
    mock_db_session.commit.assert_called_once()


def test_delete_device_model_not_found(mock_db_session):
    """Test deletion of non-existent device model"""
    from fastapi import HTTPException
    
    # Setup mock - no model found
    mock_db_session.query().filter().first.return_value = None
    
    # Call the endpoint
    with pytest.raises(HTTPException) as exc_info:
        delete_device_model(model_id=999, db=mock_db_session)
    
    assert exc_info.value.status_code == 404
    assert "機型不存在" in str(exc_info.value.detail)


def test_get_brands(mock_db_session):
    """Test retrieval of brands with Apple first"""
    # Setup mock - return distinct brands
    brands_result = [("Apple",), ("Huawei",), ("Samsung",)]
    mock_db_session.query().distinct().all.return_value = brands_result
    
    # Call the endpoint
    result = get_brands(db=mock_db_session)
    
    # Assertions - Apple should be first
    assert result[0] == "Apple"
    assert "Huawei" in result
    assert "Samsung" in result


def test_get_brands_empty(mock_db_session):
    """Test retrieval when no brands exist"""
    # Setup mock to return empty list
    mock_db_session.query().distinct().all.return_value = []
    
    # Call the endpoint
    result = get_brands(db=mock_db_session)
    
    # Assertions
    assert len(result) == 0


# ==================== Test Model Attribute Endpoints (Async) ====================

@pytest.mark.asyncio
async def test_create_model_attribute_success(mock_async_db_session):
    """Test successful creation of model attribute"""
    # Setup mock - the actual object that will be returned after refresh
    new_attr = DeviceModelAttribute(
        id=10,
        model_id=1,
        attr_type="storage",
        attr_value="256GB",
        sort_order=0
    )
    
    # Mock the async queries
    model_check_mock = MagicMock()
    model_check_mock.scalar.return_value = 1  # Model exists
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None  # No existing attribute
    
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    
    mock_async_db_session.execute.side_effect = [model_check_mock, result_mock]
    mock_async_db_session.scalars.return_value = scalars_result
    mock_async_db_session.add.return_value = None
    mock_async_db_session.commit.return_value = None
    # Mock refresh to return the new attribute with proper ID
    mock_async_db_session.refresh.return_value = new_attr  # Return the actual object
    
    # Call the endpoint
    payload = AttributeCreate(attr_type="storage", attr_value="256GB", sort_order=0)
    
    result = await create_model_attribute(model_id=1, payload=payload, db=mock_async_db_session)
    
    # Assertions - check that the returned object has correct values
    assert result.id == 10
    assert result.model_id == 1
    assert result.attr_type == "storage"
    assert result.attr_value == "256GB"


@pytest.mark.asyncio
async def test_create_model_attribute_model_not_found(mock_async_db_session):
    """Test creation fails when model doesn't exist"""
    from fastapi import HTTPException
    
    # Setup mock - model doesn't exist
    model_check_mock = MagicMock()
    model_check_mock.scalar.return_value = None  # Model doesn't exist
    
    mock_async_db_session.execute.return_value = model_check_mock
    
    # Call the endpoint
    payload = AttributeCreate(attr_type="storage", attr_value="256GB", sort_order=0)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_model_attribute(model_id=999, payload=payload, db=mock_async_db_session)
    
    assert exc_info.value.status_code == 404
    assert "機型 ID 999 不存在" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_create_model_attribute_duplicate_fails(mock_async_db_session):
    """Test that creating duplicate model attribute fails"""
    from fastapi import HTTPException
    
    # Setup mock - model exists but attribute already exists
    model_check_mock = MagicMock()
    model_check_mock.scalar.return_value = 1  # Model exists
    
    existing_attr = DeviceModelAttribute(
        id=10,
        model_id=1,
        attr_type="storage",
        attr_value="256GB",
        sort_order=0
    )
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing_attr  # Attribute exists
    
    mock_async_db_session.execute.return_value = model_check_mock
    mock_async_db_session.scalars.return_value = result_mock
    
    # Call the endpoint
    payload = AttributeCreate(attr_type="storage", attr_value="256GB", sort_order=0)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_model_attribute(model_id=1, payload=payload, db=mock_async_db_session)
    
    assert exc_info.value.status_code == 400
    assert "機型已存在屬性" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_model_attributes_all(mock_async_db_session, sample_model_attributes):
    """Test retrieval of all model attributes"""
    # Setup mock - return only attributes for model_id=1 (filtered by endpoint)
    filtered_attrs = [attr for attr in sample_model_attributes if attr.model_id == 1]
    
    scalars_result = MagicMock()
    scalars_result.all.return_value = filtered_attrs
    
    mock_async_db_session.scalars.return_value = scalars_result
    
    # Call the endpoint
    result = await get_model_attributes(model_id=1, attr_type=None, db=mock_async_db_session)
    
    # Assertions - should only return attributes for model_id=1
    assert len(result) == 2
    assert all(attr.model_id == 1 for attr in result)


@pytest.mark.asyncio
async def test_get_model_attributes_by_type(mock_async_db_session, sample_model_attributes):
    """Test retrieval of model attributes by type"""
    # Setup mock - filter by storage type
    storage_attrs = [sample_model_attributes[0]]  # Only storage type for model_id=1
    scalars_result = MagicMock()
    scalars_result.all.return_value = storage_attrs
    
    mock_async_db_session.scalars.return_value = scalars_result
    
    # Call the endpoint
    result = await get_model_attributes(model_id=1, attr_type="storage", db=mock_async_db_session)
    
    # Assertions
    assert len(result) == 1
    assert result[0].attr_type == "storage"


@pytest.mark.asyncio
async def test_get_model_attributes_empty(mock_async_db_session):
    """Test retrieval when no attributes exist"""
    # Setup mock to return empty list
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    
    mock_async_db_session.scalars.return_value = scalars_result
    
    # Call the endpoint
    result = await get_model_attributes(model_id=999, attr_type=None, db=mock_async_db_session)
    
    # Assertions
    assert len(result) == 0


@pytest.mark.asyncio
async def test_delete_attribute_success(mock_async_db_session):
    """Test successful deletion of attribute"""
    # Setup mock
    target = DeviceModelAttribute(
        id=10,
        model_id=1,
        attr_type="storage",
        attr_value="256GB",
        sort_order=0
    )
    
    scalars_result = MagicMock()
    scalars_result.first.return_value = target
    
    mock_async_db_session.scalars.return_value = scalars_result
    mock_async_db_session.delete.return_value = None
    mock_async_db_session.commit.return_value = None
    
    # Call the endpoint
    result = await delete_attribute(attr_id=10, db=mock_async_db_session)
    
    # Assertions
    assert result["message"] == "屬性 ID 10 已成功刪除"
    assert result["id"] == 10
    mock_async_db_session.delete.assert_called_once_with(target)
    mock_async_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_attribute_not_found(mock_async_db_session):
    """Test deletion of non-existent attribute"""
    from fastapi import HTTPException
    
    # Setup mock - no attribute found
    scalars_result = MagicMock()
    scalars_result.first.return_value = None
    
    mock_async_db_session.scalars.return_value = scalars_result
    
    # Call the endpoint
    with pytest.raises(HTTPException) as exc_info:
        await delete_attribute(attr_id=999, db=mock_async_db_session)
    
    assert exc_info.value.status_code == 404
    assert "未找到 ID" in str(exc_info.value.detail)


