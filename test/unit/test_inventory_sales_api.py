"""
Unit tests for inventory_sales_api.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Import the API module
from src.api.v1.endpoints.inventory_sales_api import (
    create_outbound_order,
    confirm_sell_device,
    refund_outbound_order
)
from src.model.inventory_model import InventoryModel
from src.model.order_model import OutboundOrderModel
from src.model.order_item_model import OutboundOrderItem
from src.model.staff_model import StaffModel
from src.common.dict import StockStatusEnum, PaymentStatusEnum


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def mock_current_staff():
    """Create a mock current staff user"""
    staff = MagicMock(spec=StaffModel)
    staff.shop_id = 1
    staff.id = 100
    return staff


@pytest.fixture
def mock_inventory_item():
    """Create a mock inventory item"""
    inv = MagicMock(spec=InventoryModel)
    inv.id = 1
    inv.shop_id = 1
    inv.title = "Test Device"
    inv.sn_code = "SN001"
    inv.status = StockStatusEnum.IN_STOCK.value
    inv.purchase_price = Decimal("50.00")
    return inv


@pytest.fixture
def mock_outbound_order():
    """Create a mock outbound order"""
    order = MagicMock(spec=OutboundOrderModel)
    order.id = 1
    order.shop_id = 1
    order.order_sn = "SO001"
    order.payment_status = PaymentStatusEnum.PAYED.value
    return order


@pytest.fixture
def mock_outbound_order_item():
    """Create a mock outbound order item"""
    item = MagicMock(spec=OutboundOrderItem)
    item.id = 1
    item.outbound_order_id = 1
    item.inventory_id = 1
    item.sale_price = Decimal("100.00")
    return item


class TestCreateOutboundOrder:
    """Test cases for create_outbound_order endpoint"""

    def test_create_outbound_order_success_with_auto_deliver(self, mock_db_session, mock_current_staff, mock_inventory_item):
        """Test successful outbound order creation with auto_deliver=True"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        payload.customer_id = 100
        
        item = MagicMock()
        item.inventory_id = mock_inventory_item.id
        item.sale_price = Decimal("100.00")
        payload.items = [item]
        
        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [mock_inventory_item]
        mock_db_session.flush = MagicMock()
        
        # Execute
        result = create_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert "order_id" in result
        assert "order_sn" in result
        assert result["total_amount"] == "100.00"
        mock_db_session.commit.assert_called_once()

    def test_create_outbound_order_empty_items(self, mock_db_session, mock_current_staff):
        """Test outbound order creation with empty items list"""
        payload = MagicMock()
        payload.auto_deliver = True
        payload.items = []
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            create_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "請至少選擇一項商品" in str(exc_info.value.detail)

    def test_create_outbound_order_invalid_status(self, mock_db_session, mock_current_staff):
        """Test outbound order creation with invalid inventory status"""
        payload = MagicMock()
        payload.auto_deliver = True
        payload.customer_id = 100
        
        item = MagicMock()
        item.inventory_id = 1
        item.sale_price = Decimal("100.00")
        payload.items = [item]
        
        # Mock inventory with invalid status (not IN_STOCK)
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.shop_id = 1
        inv.title = "Test Device"
        inv.status = StockStatusEnum.PENDING.value  # Invalid status
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv]
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            create_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "狀態不正確" in str(exc_info.value.detail)

    def test_create_outbound_order_database_error(self, mock_db_session, mock_current_staff):
        """Test outbound order creation with database error"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        payload.customer_id = 100
        
        item = MagicMock()
        item.inventory_id = 1
        item.sale_price = Decimal("100.00")
        payload.items = [item]
        
        # Mock inventory
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.shop_id = 1
        inv.title = "Test Device"
        inv.status = StockStatusEnum.IN_STOCK.value
        inv.purchase_price = Decimal("50.00")
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv]
        mock_db_session.flush = MagicMock()
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            create_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        # Should rollback on error
        mock_db_session.rollback.assert_called_once()

    def test_create_outbound_order_without_auto_deliver(self, mock_db_session, mock_current_staff):
        """Test outbound order creation without auto_deliver (pre-order)"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = False
        payload.customer_id = 100
        
        item = MagicMock()
        item.inventory_id = 1
        item.sale_price = Decimal("100.00")
        payload.items = [item]
        
        # Mock inventory
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.shop_id = 1
        inv.title = "Test Device"
        inv.status = StockStatusEnum.IN_STOCK.value
        inv.purchase_price = Decimal("50.00")
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv]
        mock_db_session.flush = MagicMock()
        
        # Execute
        result = create_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert "order_id" in result
        assert "order_sn" in result
        assert result["total_amount"] == "100.00"
        mock_db_session.commit.assert_called_once()

    def test_create_outbound_order_multiple_items(self, mock_db_session, mock_current_staff):
        """Test outbound order creation with multiple items"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        payload.customer_id = 100
        
        item1 = MagicMock()
        item1.inventory_id = 1
        item1.sale_price = Decimal("100.00")
        
        item2 = MagicMock()
        item2.inventory_id = 2
        item2.sale_price = Decimal("200.00")
        
        payload.items = [item1, item2]
        
        # Mock inventories
        inv1 = MagicMock(spec=InventoryModel)
        inv1.id = 1
        inv1.shop_id = 1
        inv1.title = "Device 1"
        inv1.status = StockStatusEnum.IN_STOCK.value
        inv1.purchase_price = Decimal("50.00")
        
        inv2 = MagicMock(spec=InventoryModel)
        inv2.id = 2
        inv2.shop_id = 1
        inv2.title = "Device 2"
        inv2.status = StockStatusEnum.IN_STOCK.value
        inv2.purchase_price = Decimal("100.00")
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv1, inv2]
        mock_db_session.flush = MagicMock()
        
        # Execute
        result = create_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert "order_id" in result
        assert result["total_amount"] == "300.00"
        mock_db_session.commit.assert_called_once()


class TestConfirmSellDevice:
    """Test cases for confirm_sell_device endpoint"""

    @pytest.mark.asyncio
    async def test_confirm_sell_device_success(self, mock_db_session, mock_current_staff):
        """Test successful device sale confirmation"""
        # Setup
        payload = MagicMock()
        payload.device_id = 1
        payload.price = Decimal("100.00")
        
        # Mock inventory item
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.shop_id = 1
        inv.title = "Test Device"
        inv.sn_code = "SN001"
        inv.status = StockStatusEnum.IN_STOCK.value
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = inv
        
        # Execute
        result = await confirm_sell_device(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert result["message"] == "出售成功"
        assert result["inventory_id"] == 1
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_sell_device_not_found(self, mock_db_session, mock_current_staff):
        """Test device sale confirmation when device not found"""
        # Setup
        payload = MagicMock()
        payload.device_id = 999
        payload.price = Decimal("100.00")
        
        # Mock empty result
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            await confirm_sell_device(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "設備不存在" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_confirm_sell_device_wrong_shop(self, mock_db_session, mock_current_staff):
        """Test device sale confirmation when device belongs to different shop"""
        # Setup
        payload = MagicMock()
        payload.device_id = 1
        payload.price = Decimal("100.00")
        
        # Mock inventory item from different shop
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.shop_id = 2  # Different shop
        inv.title = "Test Device"
        inv.sn_code = "SN001"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = inv
        
        # Execute and assert - should return None (not raise exception)
        result = await confirm_sell_device(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Should not find the device (filter by shop_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_confirm_sell_device_database_error(self, mock_db_session, mock_current_staff):
        """Test device sale confirmation with database error"""
        # Setup
        payload = MagicMock()
        payload.device_id = 1
        payload.price = Decimal("100.00")
        
        # Mock inventory item
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.shop_id = 1
        inv.title = "Test Device"
        inv.sn_code = "SN001"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = inv
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            await confirm_sell_device(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        # Should rollback on error
        mock_db_session.rollback.assert_called_once()


class TestRefundOutboundOrder:
    """Test cases for refund_outbound_order endpoint"""

    def test_refund_outbound_order_success(self, mock_db_session, mock_current_staff, mock_outbound_order, mock_outbound_order_item):
        """Test successful outbound order refund"""
        # Setup
        payload = MagicMock()
        payload.order_id = 1
        
        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_outbound_order
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_outbound_order_item]
        
        # Execute
        result = refund_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert result["message"] == "退貨成功"
        assert result["order_id"] == 1
        mock_db_session.commit.assert_called_once()

    def test_refund_outbound_order_not_found(self, mock_db_session, mock_current_staff):
        """Test refund when order not found"""
        # Setup
        payload = MagicMock()
        payload.order_id = 999
        
        # Mock empty result
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            refund_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "訂單不存在" in str(exc_info.value.detail)

    def test_refund_outbound_order_no_items(self, mock_db_session, mock_current_staff, mock_outbound_order):
        """Test refund when order has no items"""
        # Setup
        payload = MagicMock()
        payload.order_id = 1
        
        # Mock database queries - order exists but no items
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_outbound_order
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            refund_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "訂單無商品明細" in str(exc_info.value.detail)

    def test_refund_outbound_order_wrong_shop(self, mock_db_session, mock_current_staff):
        """Test refund when order belongs to different shop"""
        # Setup
        payload = MagicMock()
        payload.order_id = 1
        
        # Mock order from different shop
        order = MagicMock(spec=OutboundOrderModel)
        order.id = 1
        order.shop_id = 2  # Different shop
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = order
        
        # Execute and assert - should return None (not raise exception)
        result = refund_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Should not find the order (filter by shop_id)
        assert result is None

    def test_refund_outbound_order_database_error(self, mock_db_session, mock_current_staff):
        """Test refund with database error"""
        # Setup
        payload = MagicMock()
        payload.order_id = 1
        
        # Mock order
        order = MagicMock(spec=OutboundOrderModel)
        order.id = 1
        order.shop_id = 1
        order.order_sn = "SO001"
        
        # Mock order items
        item1 = MagicMock(spec=OutboundOrderItem)
        item1.inventory_id = 1
        item1.sale_price = Decimal("100.00")
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = order
        mock_db_session.query.return_value.filter.return_value.all.return_value = [item1]
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            refund_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        # Should rollback on error
        mock_db_session.rollback.assert_called_once()
        order.order_sn = "SO001"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = order
        
        # Execute and assert - should return None (not raise exception)
        result = refund_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Should not find the order (filter by shop_id)
        assert result is None

    def test_create_outbound_order_database_error(self, mock_db_session, mock_current_staff):
        """Test order creation with database error"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        
        item1 = MagicMock()
        item1.inventory_id = 1
        item1.sale_price = Decimal("100.00")
        
        item2 = MagicMock()
        item2.inventory_id = 2
        item2.sale_price = Decimal("200.00")
        
        payload.items = [item1, item2]
        payload.customer_id = None
        
        # Mock inventory items
        inv1 = MagicMock(spec=InventoryModel)
        inv1.id = 1
        inv1.shop_id = 1
        inv1.title = "Device 1"
        inv1.status = StockStatusEnum.IN_STOCK.value
        inv1.purchase_price = Decimal("50.00")
        
        inv2 = MagicMock(spec=InventoryModel)
        inv2.id = 2
        inv2.shop_id = 1
        inv2.title = "Device 2"
        inv2.status = StockStatusEnum.IN_STOCK.value
        inv2.purchase_price = Decimal("100.00")
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv1, inv2]
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            create_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        # Should rollback on error
        mock_db_session.rollback.assert_called_once()

    def test_create_outbound_order_no_items(self, mock_db_session, mock_current_staff):
        """Test order creation with no items"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        payload.items = []  # Empty list
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            create_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "請至少選擇一項商品" in str(exc_info.value.detail)

    def test_create_outbound_order_invalid_status(self, mock_db_session, mock_current_staff):
        """Test order creation with invalid inventory status"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        
        item1 = MagicMock()
        item1.inventory_id = 1
        item1.sale_price = Decimal("100.00")
        
        payload.items = [item1]
        payload.customer_id = None
        
        # Mock inventory with invalid status (not IN_STOCK)
        inv1 = MagicMock(spec=InventoryModel)
        inv1.id = 1
        inv1.shop_id = 1
        inv1.title = "Device 1"
        inv1.status = StockStatusEnum.PENDING.value  # Not in stock
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv1]
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            create_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "狀態不正確" in str(exc_info.value.detail)

    def test_confirm_sell_device_database_error(self, mock_db_session, mock_current_staff):
        """Test device sell confirmation with database error"""
        # Setup
        payload = MagicMock()
        payload.device_id = 1
        payload.price = Decimal("100.00")
        
        # Mock device
        device = MagicMock(spec=InventoryModel)
        device.id = 1
        device.shop_id = 1
        device.sn_code = "SN001"
        device.title = "Device 1"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = device
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            asyncio.run(confirm_sell_device(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            ))
        
        # Should rollback on error
        mock_db_session.rollback.assert_called_once()

    def test_confirm_sell_device_not_found(self, mock_db_session, mock_current_staff):
        """Test device sell confirmation when device not found"""
        # Setup
        payload = MagicMock()
        payload.device_id = 999
        payload.price = Decimal("100.00")
        
        # Mock empty result
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            asyncio.run(confirm_sell_device(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            ))
        
        assert "設備不存在" in str(exc_info.value.detail)

    def test_refund_outbound_order_not_found(self, mock_db_session, mock_current_staff):
        """Test refund when order not found"""
        # Setup
        payload = MagicMock()
        payload.order_id = 999
        
        # Mock empty result
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            refund_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "訂單不存在" in str(exc_info.value.detail)

    def test_refund_outbound_order_no_items(self, mock_db_session, mock_current_staff):
        """Test refund when order has no items"""
        # Setup
        payload = MagicMock()
        payload.order_id = 1
        
        # Mock order
        order = MagicMock(spec=OutboundOrderModel)
        order.id = 1
        order.shop_id = 1
        order.order_sn = "SO001"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = order
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Execute and assert
        with pytest.raises(Exception) as exc_info:
            refund_outbound_order(
                payload=payload,
                db=mock_db_session,
                current_staff=mock_current_staff
            )
        
        assert "訂單無商品明細" in str(exc_info.value.detail)

    def test_create_outbound_order_success(self, mock_db_session, mock_current_staff):
        """Test successful order creation with auto_deliver=True"""
        # Setup
        payload = MagicMock()
        payload.auto_deliver = True
        
        item1 = MagicMock()
        item1.inventory_id = 1
        item1.sale_price = Decimal("100.00")
        
        item2 = MagicMock()
        item2.inventory_id = 2
        item2.sale_price = Decimal("200.00")
        
        payload.items = [item1, item2]
        payload.customer_id = None
        
        # Mock inventory items
        inv1 = MagicMock(spec=InventoryModel)
        inv1.id = 1
        inv1.shop_id = 1
        inv1.title = "Device 1"
        inv1.status = StockStatusEnum.IN_STOCK.value
        inv1.purchase_price = Decimal("50.00")
        
        inv2 = MagicMock(spec=InventoryModel)
        inv2.id = 2
        inv2.shop_id = 1
        inv2.title = "Device 2"
        inv2.status = StockStatusEnum.IN_STOCK.value
        inv2.purchase_price = Decimal("100.00")
        
        mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [inv1, inv2]
        mock_db_session.flush.return_value = None  # No ID to return
        
        # Execute and assert
        result = create_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Should succeed
        assert "order_id" in result
        assert "order_sn" in result
        assert result["total_amount"] == "300.00"
        assert result["total_profit"] == "150.00"
        
        # Should commit successfully
        mock_db_session.commit.assert_called_once()

    def test_confirm_sell_device_success(self, mock_db_session, mock_current_staff):
        """Test successful device sell confirmation"""
        # Setup
        payload = MagicMock()
        payload.device_id = 1
        payload.price = Decimal("100.00")
        
        # Mock device
        device = MagicMock(spec=InventoryModel)
        device.id = 1
        device.shop_id = 1
        device.sn_code = "SN001"
        device.title = "Device 1"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = device
        
        # Execute and assert
        result = asyncio.run(confirm_sell_device(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        ))
        
        # Should succeed
        assert "message" in result
        assert result["inventory_id"] == 1
        
        # Device status should be updated to SOLD
        assert device.status == StockStatusEnum.SOLD.value
        
        # Should commit successfully
        mock_db_session.commit.assert_called_once()

    def test_refund_outbound_order_success(self, mock_db_session, mock_current_staff):
        """Test successful refund processing"""
        # Setup
        payload = MagicMock()
        payload.order_id = 1
        
        # Mock order
        order = MagicMock(spec=OutboundOrderModel)
        order.id = 1
        order.shop_id = 1
        order.order_sn = "SO001"
        
        # Mock order items
        item1 = MagicMock()
        item1.inventory_id = 1
        item1.sale_price = Decimal("100.00")
        
        item2 = MagicMock()
        item2.inventory_id = 2
        item2.sale_price = Decimal("200.00")
        
        # Mock inventory items
        inv1 = MagicMock(spec=InventoryModel)
        inv1.id = 1
        inv1.shop_id = 1
        inv1.title = "Device 1"
        
        inv2 = MagicMock(spec=InventoryModel)
        inv2.id = 2
        inv2.shop_id = 1
        inv2.title = "Device 2"
        
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            order,  # First call for order
            inv1,   # Second call for item1 inventory
            inv2    # Third call for item2 inventory
        ]
        mock_db_session.query.return_value.filter.return_value.all.return_value = [item1, item2]
        
        # Execute and assert
        result = refund_outbound_order(
            payload=payload,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Should succeed
        assert "message" in result
        assert result["order_id"] == 1
        
        # Order status should be updated to RETURNED
        assert order.status == 3
        
        # Inventory items should be updated to RETURNED status
        assert inv1.status == StockStatusEnum.RETURNED.value
        assert inv2.status == StockStatusEnum.RETURNED.value
        
        # Should commit successfully
        mock_db_session.commit.assert_called_once()
