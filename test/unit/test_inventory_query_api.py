"""
Unit tests for inventory_query_api.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Import the API module
from src.api.v1.endpoints.inventory_query_api import (
    get_inventory_list,
    search_inventory_by_sn,
    get_sales_detail,
    get_inventory_detail,
    get_device_options
)
from src.model.inventory_model import InventoryModel
from src.model.device_models import DeviceModel, DeviceModelAttribute
from src.model.staff_model import StaffModel
from src.model.order_model import OutboundOrderModel
from src.model.order_item_model import OutboundOrderItem
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


@pytest.fixture
def mock_inventory():
    """Create a mock inventory item"""
    # Create a non-spec mock to allow dynamic attribute access
    inventory = MagicMock()
    inventory.id = 1
    inventory.device_sn = "SN123456789"
    inventory.shop_id = 1
    inventory.status = StockStatusEnum.IN_STOCK.value
    return inventory


@pytest.fixture
def mock_order():
    """Create a mock order"""
    order = MagicMock(spec=OutboundOrderModel)
    order.id = 1
    order.shop_id = 1
    order.order_sn = "ORDER123456"
    return order


@pytest.fixture
def mock_order_item():
    """Create a mock order item"""
    # Create a non-spec mock to allow dynamic attribute access
    item = MagicMock()
    item.id = 1
    item.outbound_order_id = 1
    item.device_sn = "SN123456789"
    return item


@pytest.fixture
def mock_device_model():
    """Create a mock device model"""
    model = MagicMock(spec=DeviceModel)
    model.id = 1
    model.name = "iPhone 15"
    return model


@pytest.fixture
def mock_device_attribute():
    """Create a mock device attribute"""
    attr = MagicMock(spec=DeviceModelAttribute)
    attr.id = 1
    attr.name = "Color"
    return attr


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
def test_get_inventory_list_success(mock_get_current_staff, mock_db_session, mock_current_staff, mock_inventory):
    """Test successful inventory list retrieval"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock query result
    inventories = [mock_inventory]
    mock_db_session.query.return_value.filter.return_value.all.return_value = inventories
    
    # Execute
    result = get_inventory_list(db=mock_db_session, current_staff=mock_current_staff)
    
    # Assert
    assert result == {"items": inventories}
    mock_db_session.query.assert_called_once_with(InventoryModel)


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
def test_get_inventory_list_empty(mock_get_current_staff, mock_db_session, mock_current_staff):
    """Test inventory list retrieval when no items exist"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock empty query result
    mock_db_session.query.return_value.filter.return_value.all.return_value = []
    
    # Execute
    result = get_inventory_list(db=mock_db_session, current_staff=mock_current_staff)
    
    # Assert
    assert result == {"items": []}


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
def test_get_inventory_list_exception(mock_get_current_staff, mock_db_session, mock_current_staff):
    """Test inventory list retrieval with database exception"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock exception
    mock_db_session.query.side_effect = Exception("Database error")
    
    # Execute & Assert
    with pytest.raises(Exception):
        get_inventory_list(db=mock_db_session, current_staff=mock_current_staff)


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
def test_search_inventory_by_sn_success(mock_get_current_staff, mock_db_session, mock_current_staff, mock_inventory):
    """Test successful inventory search by SN"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock the InventoryModel class to have device_sn attribute
    with patch('src.api.v1.endpoints.inventory_query_api.InventoryModel') as mock_inv_model:
        mock_inv_model.device_sn = "SN123456789"
        mock_inv_model.shop_id = 1
        # Mock query result
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_inventory
        
        # Execute
        result = search_inventory_by_sn(
            device_sn="SN123456789",
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assert
        assert result == mock_inventory
        mock_db_session.query.assert_called_once_with(mock_inv_model)


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
def test_search_inventory_by_sn_not_found(mock_get_current_staff, mock_db_session, mock_current_staff):
    """Test inventory search by SN when item not found"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock empty query result
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Execute & Assert
    with pytest.raises(Exception):
        search_inventory_by_sn(
            device_sn="SN999999999",
            db=mock_db_session,
            current_staff=mock_current_staff
        )


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
def test_search_inventory_by_sn_exception(mock_get_current_staff, mock_db_session, mock_current_staff):
    """Test inventory search by SN with database exception"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock exception
    mock_db_session.query.side_effect = Exception("Database error")
    
    # Execute & Assert
    with pytest.raises(Exception):
        search_inventory_by_sn(
            device_sn="SN123456789",
            db=mock_db_session,
            current_staff=mock_current_staff
        )


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
async def test_get_sales_detail_success(mock_get_current_staff, mock_async_db_session, mock_current_staff, mock_order, mock_order_item):
    """Test successful sales detail retrieval"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock async get result
    mock_async_db_session.get.return_value = mock_order
    
    # Mock the entire execute call for order items
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [mock_order_item]
    mock_async_db_session.execute.return_value = mock_execute_result

    # Execute
    result = await get_sales_detail(
        order_id=1,
        db=mock_async_db_session,
        current_staff=mock_current_staff
    )

    # Assert
    assert result["order"] == mock_order
    assert result["items"] == [mock_order_item]
    mock_async_db_session.get.assert_called_once_with(OutboundOrderModel, 1)


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
async def test_get_sales_detail_not_found(mock_get_current_staff, mock_async_db_session, mock_current_staff):
    """Test sales detail retrieval when order not found"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock async get result (not found)
    mock_async_db_session.get.return_value = None
    
    # Execute & Assert
    with pytest.raises(Exception):
        await get_sales_detail(
            order_id=999,
            db=mock_async_db_session,
            current_staff=mock_current_staff
        )


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
async def test_get_sales_detail_exception(mock_get_current_staff, mock_async_db_session, mock_current_staff):
    """Test sales detail retrieval with database exception"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock exception
    mock_async_db_session.get.side_effect = Exception("Database error")
    
    # Execute & Assert
    with pytest.raises(Exception):
        await get_sales_detail(
            order_id=1,
            db=mock_async_db_session,
            current_staff=mock_current_staff
        )


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
async def test_get_inventory_detail_success(mock_get_current_staff, mock_async_db_session, mock_current_staff, mock_inventory):
    """Test successful inventory detail retrieval"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock async get result
    mock_async_db_session.get.return_value = mock_inventory
    
    # Execute
    result = await get_inventory_detail(
        target_id=1,
        db=mock_async_db_session,
        current_staff=mock_current_staff
    )
    
    # Assert
    assert result == mock_inventory
    mock_async_db_session.get.assert_called_once_with(InventoryModel, 1)


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
async def test_get_inventory_detail_not_found(mock_get_current_staff, mock_async_db_session, mock_current_staff):
    """Test inventory detail retrieval when item not found"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock async get result (not found)
    mock_async_db_session.get.return_value = None
    
    # Execute & Assert
    with pytest.raises(Exception):
        await get_inventory_detail(
            target_id=999,
            db=mock_async_db_session,
            current_staff=mock_current_staff
        )


@patch('src.api.v1.endpoints.inventory_query_api.get_current_staff')
async def test_get_inventory_detail_exception(mock_get_current_staff, mock_async_db_session, mock_current_staff):
    """Test inventory detail retrieval with database exception"""
    # Setup
    mock_get_current_staff.return_value = mock_current_staff
    
    # Mock exception
    mock_async_db_session.get.side_effect = Exception("Database error")
    
    # Execute & Assert
    with pytest.raises(Exception):
        await get_inventory_detail(
            target_id=1,
            db=mock_async_db_session,
            current_staff=mock_current_staff
        )


async def test_get_device_options_success(mock_async_db_session, mock_device_model, mock_device_attribute):
    """Test successful device options retrieval"""
    # Mock async execute results
    mock_models_result = MagicMock()
    mock_models_result.scalars.return_value.all.return_value = [mock_device_model]
    
    mock_attributes_result = MagicMock()
    mock_attributes_result.scalars.return_value.all.return_value = [mock_device_attribute]
    
    mock_async_db_session.execute.side_effect = [mock_models_result, mock_attributes_result]
    
    # Execute
    result = await get_device_options(db=mock_async_db_session)
    
    # Assert
    assert "models" in result
    assert "attributes" in result
    assert len(result["models"]) == 1
    assert len(result["attributes"]) == 1
    assert result["models"][0]["id"] == 1
    assert result["models"][0]["name"] == "iPhone 15"
    assert result["attributes"][0]["id"] == 1
    assert result["attributes"][0]["name"] == "Color"


async def test_get_device_options_empty(mock_async_db_session):
    """Test device options retrieval when no items exist"""
    # Mock empty async execute results
    mock_models_result = MagicMock()
    mock_models_result.scalars.return_value.all.return_value = []
    
    mock_attributes_result = MagicMock()
    mock_attributes_result.scalars.return_value.all.return_value = []
    
    mock_async_db_session.execute.side_effect = [mock_models_result, mock_attributes_result]
    
    # Execute
    result = await get_device_options(db=mock_async_db_session)
    
    # Assert
    assert len(result["models"]) == 0
    assert len(result["attributes"]) == 0


async def test_get_device_options_exception(mock_async_db_session):
    """Test device options retrieval with database exception"""
    # Mock exception
    mock_async_db_session.execute.side_effect = Exception("Database error")
    
    # Execute & Assert
    with pytest.raises(Exception):
        await get_device_options(db=mock_async_db_session)
