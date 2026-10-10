"""
Unit tests for inventory_device_api.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Import the API module
from src.api.v1.endpoints.inventory_device_api import (
    confirm_add_device,
    confirm_add_detailed_device,
    get_device_options,
    DetailedDeviceItem,
    CreateDetailedPurchasePayload
)
from src.model.inventory_model import InventoryModel
from src.model.device_models import DeviceModel, DeviceModelAttribute
from src.model.staff_model import StaffModel
from src.common.dict import StockStatusEnum


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def mock_async_db_session():
    """Create a mock async database session"""
    db = MagicMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_current_staff():
    """Create a mock current staff user"""
    staff = MagicMock(spec=StaffModel)
    staff.shop_id = 1
    staff.id = 100
    return staff


@pytest.mark.asyncio
async def test_confirm_add_device_success(mock_db_session, mock_current_staff):
    """Test successful device addition to inventory"""
    # Setup test data
    device_sn = "TEST123456"
    purchase_price = Decimal("100.00")
    model_id = 5
    color = "black"
    storage = "128GB"
    
    # Create mock device
    device = MagicMock(spec=InventoryModel)
    device.id = 1
    device.device_sn = device_sn
    device.shop_id = 1
    device.status = StockStatusEnum.PENDING.value
    
    # Mock query results
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = device
    mock_db_session.query.return_value = mock_query
    
    # Create payload
    from src.model.inventory_schema import AddDeviceConfirmPayload
    payload = AddDeviceConfirmPayload(
        device_sn=device_sn,
        purchase_price=purchase_price,
        model_id=model_id,
        color=color,
        storage=storage
    )
    
    # Call the endpoint
    result = await confirm_add_device(payload, db=mock_db_session, current_staff=mock_current_staff)
    
    # Assertions
    assert result["message"] == "入庫成功"
    assert result["device_id"] == device.id
    
    # Verify device updates
    assert device.status == StockStatusEnum.IN_STOCK.value
    assert device.purchase_price == purchase_price
    assert device.model_id == model_id
    assert device.color == color
    assert device.storage == storage
    
    # Verify database operations
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_add_device_not_found(mock_db_session, mock_current_staff):
    """Test device addition when device doesn't exist"""
    from fastapi import HTTPException
    from src.model.inventory_schema import AddDeviceConfirmPayload
    
    # Setup test data
    device_sn = "NOTFOUND123"
    payload = AddDeviceConfirmPayload(
        device_sn=device_sn,
        purchase_price=Decimal("100.00"),
        model_id=5,
        color="black",
        storage="128GB"
    )
    
    # Mock query to return None
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_db_session.query.return_value = mock_query
    
    # Call the endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await confirm_add_device(payload, db=mock_db_session, current_staff=mock_current_staff)
    
    assert exc_info.value.status_code == 404
    assert "設備不存在" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_confirm_add_device_exception(mock_db_session, mock_current_staff):
    """Test device addition with database exception"""
    from fastapi import HTTPException
    from src.model.inventory_schema import AddDeviceConfirmPayload
    
    # Setup test data
    device_sn = "ERROR123456"
    payload = AddDeviceConfirmPayload(
        device_sn=device_sn,
        purchase_price=Decimal("100.00"),
        model_id=5,
        color="black",
        storage="128GB"
    )
    
    # Create mock device
    device = MagicMock(spec=InventoryModel)
    device.id = 1
    device.device_sn = device_sn
    device.shop_id = 1
    device.status = StockStatusEnum.PENDING.value
    
    # Mock query results
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = device
    mock_db_session.query.return_value = mock_query
    
    # Simulate database exception
    mock_db_session.commit.side_effect = Exception("Database error")
    
    # Call the endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await confirm_add_device(payload, db=mock_db_session, current_staff=mock_current_staff)
    
    assert exc_info.value.status_code == 500
    assert "入庫失敗" in str(exc_info.value.detail)
    mock_db_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_add_detailed_device_success(mock_db_session, mock_current_staff):
    """Test successful batch device addition with detailed information"""
    # Setup test data
    items = [
        DetailedDeviceItem(
            device_sn="TEST123456",
            model_id=5,
            color="black",
            storage="128GB",
            purchase_price=Decimal("100.00")
        ),
        DetailedDeviceItem(
            device_sn="TEST789012",
            model_id=6,
            color="white",
            storage="256GB",
            purchase_price=Decimal("150.00")
        )
    ]
    
    payload = CreateDetailedPurchasePayload(items=items)
    
    # Create mock devices
    device1 = MagicMock(spec=InventoryModel)
    device1.id = 1
    device1.device_sn = "TEST123456"
    device1.shop_id = 1
    device1.status = StockStatusEnum.PENDING.value
    
    device2 = MagicMock(spec=InventoryModel)
    device2.id = 2
    device2.device_sn = "TEST789012"
    device2.shop_id = 1
    device2.status = StockStatusEnum.PENDING.value
    
    # Mock query results - different for each device
    def mock_filter_side_effect(*args, **kwargs):
        filter_mock = MagicMock()
        for arg in args:
            if hasattr(arg, '__eq__'):
                if 'TEST123456' in str(arg):
                    filter_mock.first.return_value = device1
                elif 'TEST789012' in str(arg):
                    filter_mock.first.return_value = device2
        return filter_mock
    
    mock_query = MagicMock()
    mock_query.filter.side_effect = mock_filter_side_effect
    mock_db_session.query.return_value = mock_query
    
    # Call the endpoint
    result = await confirm_add_detailed_device(payload, db=mock_db_session, current_staff=mock_current_staff)
    
    # Assertions
    assert result["message"] == "批量入庫成功"
    assert result["count"] == 2
    
    # Verify device updates
    assert device1.status == StockStatusEnum.IN_STOCK.value
    assert device1.purchase_price == Decimal("100.00")
    assert device2.status == StockStatusEnum.IN_STOCK.value
    assert device2.purchase_price == Decimal("150.00")
    
    # Verify database operations
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_add_detailed_device_one_not_found(mock_db_session, mock_current_staff):
    """Test batch device addition when one device doesn't exist"""
    from fastapi import HTTPException
    
    # Setup test data with one invalid device
    items = [
        DetailedDeviceItem(
            device_sn="TEST123456",
            model_id=5,
            color="black",
            storage="128GB",
            purchase_price=Decimal("100.00")
        ),
        DetailedDeviceItem(
            device_sn="NOTFOUND789",
            model_id=6,
            color="white",
            storage="256GB",
            purchase_price=Decimal("150.00")
        )
    ]
    
    payload = CreateDetailedPurchasePayload(items=items)
    
    # Create mock device (only one exists)
    device1 = MagicMock(spec=InventoryModel)
    device1.id = 1
    device1.device_sn = "TEST123456"
    device1.shop_id = 1
    device1.status = StockStatusEnum.PENDING.value
    
    # Mock query results - only first device exists
    def mock_filter_side_effect(*args, **kwargs):
        filter_mock = MagicMock()
        for arg in args:
            if hasattr(arg, '__eq__'):
                if 'TEST123456' in str(arg):
                    filter_mock.first.return_value = device1
                elif 'NOTFOUND789' in str(arg):
                    filter_mock.first.return_value = None
        return filter_mock
    
    mock_query = MagicMock()
    mock_query.filter.side_effect = mock_filter_side_effect
    mock_db_session.query.return_value = mock_query
    
    # Call the endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await confirm_add_detailed_device(payload, db=mock_db_session, current_staff=mock_current_staff)
    
    assert exc_info.value.status_code == 404
    assert "NOTFOUND789" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_device_options_success(mock_async_db_session):
    """Test successful retrieval of device options"""
    # Create mock models
    model1 = MagicMock(spec=DeviceModel)
    model1.id = 5
    model1.name = "iPhone 13"
    
    model2 = MagicMock(spec=DeviceModel)
    model2.id = 6
    model2.name = "iPhone 14"
    
    # Create mock global attributes
    global_color = MagicMock(spec=DeviceModelAttribute)
    global_color.id = 1
    global_color.model_id = None
    global_color.attribute_type = "color"
    global_color.value = "black"
    
    global_storage = MagicMock(spec=DeviceModelAttribute)
    global_storage.id = 2
    global_storage.model_id = None
    global_storage.attribute_type = "storage"
    global_storage.value = "128GB"
    
    # Create mock model-specific attributes
    model_specific_color = MagicMock(spec=DeviceModelAttribute)
    model_specific_color.id = 3
    model_specific_color.model_id = 5
    model_specific_color.attribute_type = "color"
    model_specific_color.value = "blue"
    
    model_specific_storage = MagicMock(spec=DeviceModelAttribute)
    model_specific_storage.id = 4
    model_specific_storage.model_id = 5
    model_specific_storage.attribute_type = "storage"
    model_specific_storage.value = "256GB"
    
    # Mock execute results
    models_result = MagicMock()
    models_result.scalars.return_value.all.return_value = [model1, model2]
    
    global_attrs_result = MagicMock()
    global_attrs_result.scalars.return_value.all.return_value = [global_color, global_storage]
    
    model_specific_attrs_result = MagicMock()
    model_specific_attrs_result.scalars.return_value.all.return_value = [model_specific_color, model_specific_storage]
    
    mock_async_db_session.execute.side_effect = [
        models_result,
        global_attrs_result,
        model_specific_attrs_result
    ]
    
    # Call the endpoint
    result = await get_device_options(db=mock_async_db_session)
    
    # Assertions
    assert "models" in result
    assert len(result["models"]) == 2
    assert result["models"][0]["id"] == 5
    assert result["models"][0]["name"] == "iPhone 13"
    
    assert "global_attributes" in result
    assert "colors" in result["global_attributes"]
    assert "storages" in result["global_attributes"]
    assert "black" in result["global_attributes"]["colors"]
    assert "128GB" in result["global_attributes"]["storages"]
    
    assert "model_specific_attributes" in result
    assert 5 in result["model_specific_attributes"]
    assert "blue" in result["model_specific_attributes"][5]["colors"]
    assert "256GB" in result["model_specific_attributes"][5]["storages"]


@pytest.mark.asyncio
async def test_get_device_options_exception(mock_async_db_session):
    """Test device options retrieval with database exception"""
    from fastapi import HTTPException
    
    # Simulate database exception
    mock_async_db_session.execute.side_effect = Exception("Database error")
    
    # Call the endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await get_device_options(db=mock_async_db_session)
    
    assert exc_info.value.status_code == 500
    assert "查詢失敗" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_confirm_add_device_financial_record_creation(mock_db_session, mock_current_staff):
    """Test that financial record is created when device is added"""
    from src.model.inventory_schema import AddDeviceConfirmPayload
    from src.model.models import FinancialRecord
    
    # Setup test data
    device_sn = "FINANCE123"
    purchase_price = Decimal("200.00")
    
    # Create mock device
    device = MagicMock(spec=InventoryModel)
    device.id = 1
    device.device_sn = device_sn
    device.shop_id = 1
    device.status = StockStatusEnum.PENDING.value
    
    # Mock query results
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = device
    mock_db_session.query.return_value = mock_query
    
    payload = AddDeviceConfirmPayload(
        device_sn=device_sn,
        purchase_price=purchase_price,
        model_id=5,
        color="black",
        storage="128GB"
    )
    
    # Call the endpoint
    result = await confirm_add_device(payload, db=mock_db_session, current_staff=mock_current_staff)
    
    # Verify financial record was created and added to session
    mock_db_session.add.assert_called()
    call_args = mock_db_session.add.call_args
    assert isinstance(call_args[0][0], FinancialRecord)
    financial_record = call_args[0][0]
    assert financial_record.shop_id == 1
    assert financial_record.amount == -purchase_price  # Negative for expense
    assert financial_record.category == "purchase"
    assert device_sn in financial_record.description
