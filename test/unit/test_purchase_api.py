"""
Unit tests for purchase_api.py
"""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Import the API module
from src.api.v1.endpoints.purchase_api import (
    get_order_list,
    get_purchase_detail,
    confirm_inbound
)
from src.model.inventory_model import InventoryModel
from src.model.partner_model import Partner as PartnerModel
from src.model.staff_model import StaffModel
from src.model.order_model import OutboundOrderModel
from src.model.order_item_model import OutboundOrderItem
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
    """Create a mock inventory item (purchase/inbound order)"""
    inv = MagicMock(spec=InventoryModel)
    inv.id = 1
    inv.shop_id = 1
    inv.title = "iPhone 13"
    inv.sn_code = "IMEI1234567890"
    inv.category = 1
    inv.status = StockStatusEnum.IN_STOCK.value  # Changed from PENDING to IN_STOCK for default queries
    inv.supplier_id = 10
    inv.purchase_price = Decimal("100.00")
    inv.created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    return inv


@pytest.fixture
def mock_partner():
    """Create a mock partner/supplier"""
    partner = MagicMock(spec=PartnerModel)
    partner.id = 10
    partner.name = "Tech Supplier Co."
    partner.phone = "13800000000"
    return partner


@pytest.fixture
def mock_outbound_order():
    """Create a mock outbound order (sales/outbound order)"""
    order = MagicMock(spec=OutboundOrderModel)
    order.id = 100
    order.shop_id = 2  # Match the staff's shop_id in tests
    order.order_sn = "SO20240101"
    order.customer_id = 20
    order.total_amount = Decimal("200.00")
    order.total_profit = Decimal("50.00")
    order.payment_status = PaymentStatusEnum.PAYED.value
    order.created_at = datetime(2024, 1, 16, 14, 45, 0, tzinfo=timezone.utc)
    return order


@pytest.fixture
def mock_customer():
    """Create a mock customer"""
    customer = MagicMock(spec=PartnerModel)
    customer.id = 20
    customer.name = "John Doe"
    customer.phone = "13911111111"
    return customer


class TestGetOrderList:
    """Test cases for get_order_list endpoint"""

    def test_get_order_list_all_types(self, mock_db_session, mock_current_staff,
                                       mock_inventory_item, mock_partner,
                                       mock_outbound_order, mock_customer):
        """Test getting all order types (purchase and sales)"""
        # Setup inventory query for purchase orders
        inv_query_mock = MagicMock()
        inv_query_mock.outerjoin.return_value.filter.return_value.all.return_value = [(mock_inventory_item, mock_partner)]
    
        # Setup outbound order query for sales orders
        order_query_mock = MagicMock()
        order_query_mock.outerjoin.return_value.outerjoin.return_value.filter.return_value.group_by.return_value.all.return_value = [
            (mock_outbound_order, mock_customer, 1)
        ]
    
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            print(f"Query called with args: {args}, kwargs: {kwargs}")
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                return inv_query_mock
            else:
                print("Returning order_query_mock")
                return order_query_mock
    
        mock_db_session.query.side_effect = get_query_side_effect
        
        # Execute
        result = get_order_list(
            order_type=None,
            status=None,
            keyword=None,
            page=1,
            page_size=20,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Debug output
        print(f"Result total: {result['total']}")
        print(f"Result items count: {len(result['items'])}")
        for i, item in enumerate(result['items']):
            print(f"Item {i}: order_type={item['order_type']}, id={item.get('id')}")
        
        # Assertions
        assert result["total"] == 2
        assert len(result["items"]) == 2
        
        # Check purchase order in results
        purchase_order = [item for item in result["items"] if item["order_type"] == 1][0]
        assert purchase_order["id"] == mock_inventory_item.id
        assert purchase_order["title"] == "iPhone 13"
        assert purchase_order["order_sn"] == "IN-1"
        assert purchase_order["type_name"] == "進貨入庫"
        assert purchase_order["partner_name"] == "Tech Supplier Co."
        assert purchase_order["total_amount"] == 100.0
        
        # Check sales order in results
        sales_order = [item for item in result["items"] if item["order_type"] == 2][0]
        assert sales_order["id"] == mock_outbound_order.id
        assert sales_order["order_sn"] == "SO20240101"
        assert sales_order["type_name"] == "銷售出庫"
        assert sales_order["partner_name"] == "John Doe"
        assert sales_order["total_amount"] == 200.0
        assert sales_order["order_item_count"] == 1

    def test_get_order_list_filter_by_type_purchase(self, mock_db_session, mock_current_staff,
                                                     mock_inventory_item, mock_partner):
        """Test filtering orders by type (purchase only)"""
        # Setup inventory query - mock the entire chain
        inv_query = MagicMock()
        inv_query.outerjoin.return_value.filter.return_value.all.return_value = [(mock_inventory_item, mock_partner)]
    
        # Mock the status attribute to return a proper value
        mock_inventory_item.status = StockStatusEnum.PENDING.value
        mock_inventory_item.id = 123
        mock_inventory_item.title = "Test Device"
        mock_inventory_item.category = "Phone"
        mock_inventory_item.sn_code = "SN-001"
    
        # Mock partner data
        mock_partner.name = "Supplier Co."
        mock_partner.phone = "1234567890"
    
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                return inv_query
            else:
                # For sales orders, return empty
                order_query = MagicMock()
                order_query.group_by.return_value.all.return_value = []
                order_filter_mock = MagicMock()
                order_filter_mock.outerjoin.return_value.outerjoin.return_value = order_query
                return order_filter_mock
    
        mock_db_session.query.side_effect = get_query_side_effect
    
        # Execute - only purchase orders
        result = get_order_list(
            order_type=1,
            status=None,
            keyword=None,
            page=1,
            page_size=20,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
    
        # Assertions
        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["order_type"] == 1

    def test_get_order_list_filter_by_status_pending(self, mock_db_session, mock_current_staff,
                                                       mock_partner):
        """Test filtering purchase orders by status (pending only)"""
        # Create a separate mock inventory item with PENDING status for this specific test
        pending_inv = MagicMock(spec=InventoryModel)
        pending_inv.id = 1
        pending_inv.shop_id = 1
        pending_inv.title = "iPhone 13"
        pending_inv.sn_code = "IMEI1234567890"
        pending_inv.category = 1
        pending_inv.status = StockStatusEnum.PENDING.value
        pending_inv.supplier_id = 10
        pending_inv.purchase_price = Decimal("100.00")
        pending_inv.created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        # Setup inventory query - mock the entire chain
        inv_query = MagicMock()
        inv_query.outerjoin.return_value.filter.return_value.all.return_value = [(pending_inv, mock_partner)]
        
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                return inv_query
            else:
                # For sales orders, return empty
                order_query = MagicMock()
                order_query.group_by.return_value.all.return_value = []
                order_filter_mock = MagicMock()
                order_filter_mock.outerjoin.return_value.outerjoin.return_value = order_query
                return order_filter_mock
        
        mock_db_session.query.side_effect = get_query_side_effect
        
        # Execute - only pending purchase orders
        result = get_order_list(
            order_type=1,
            status=StockStatusEnum.PENDING,
            keyword=None,
            page=1,
            page_size=20,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["status"] == StockStatusEnum.PENDING.value

    def test_get_order_list_with_keyword_search(self, mock_db_session, mock_current_staff,
                                                 mock_inventory_item, mock_partner):
        """Test searching orders by keyword"""
        # Setup inventory query - mock the entire chain
        inv_query = MagicMock()
        filter_mock = MagicMock()
        filter_mock.all.return_value = [(mock_inventory_item, mock_partner)]
        
        # Mock the status attribute to return a proper value
        mock_inventory_item.status = StockStatusEnum.PENDING.value
        
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                # Return the base query that can be filtered twice
                base_query = MagicMock()
                first_filter = MagicMock()
                second_filter = MagicMock()
                second_filter.all.return_value = [(mock_inventory_item, mock_partner)]
                
                # Setup chain: outerjoin -> filter (shop_id, status) -> filter (keyword)
                base_query.outerjoin.return_value.filter.return_value = first_filter
                first_filter.filter.return_value = second_filter
                return base_query
            else:
                # For sales orders, return empty
                order_query = MagicMock()
                order_query.group_by.return_value.all.return_value = []
                order_filter_mock = MagicMock()
                order_filter_mock.outerjoin.return_value.outerjoin.return_value = order_query
                return MagicMock(return_value=order_filter_mock)
        
        mock_db_session.query.side_effect = get_query_side_effect
        
        # Execute - search by keyword "iPhone"
        result = get_order_list(
            order_type=None,
            status=None,
            keyword="iPhone",
            page=1,
            page_size=20,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert "iPhone" in result["items"][0]["title"]

    def test_get_order_list_pagination(self, mock_db_session, mock_current_staff,
                                        mock_inventory_item, mock_partner):
        """Test pagination of order list"""
        # Create multiple inventory items
        inv2 = MagicMock(spec=InventoryModel)
        inv2.id = 2
        inv2.shop_id = 1
        inv2.title = "iPhone 14"
        inv2.sn_code = "IMEI9876543210"
        inv2.category = 1
        inv2.status = StockStatusEnum.PENDING.value
        inv2.supplier_id = 10
        inv2.purchase_price = Decimal("150.00")
        inv2.created_at = datetime(2024, 1, 14, 9, 30, 0, tzinfo=timezone.utc)
        
        # Mock the status attribute to return a proper value
        mock_inventory_item.status = StockStatusEnum.PENDING.value
        
        # Setup inventory query with proper filter chain
        inv_query_mock = MagicMock()
        inv_query_mock.outerjoin.return_value.filter.return_value.all.return_value = [(mock_inventory_item, mock_partner), (inv2, mock_partner)]
        
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                return inv_query_mock
            else:
                # For sales orders, return empty
                order_query = MagicMock()
                order_query.group_by.return_value.all.return_value = []
                order_filter_mock = MagicMock()
                order_filter_mock.outerjoin.return_value.outerjoin.return_value = order_query
                return order_filter_mock
        
        mock_db_session.query.side_effect = get_query_side_effect
        
        # Execute - page 1 with size 1
        result = get_order_list(
            order_type=None,
            status=None,
            keyword=None,
            page=1,
            page_size=1,
            db=mock_db_session,
            current_staff=mock_current_staff
        )
        
        # Assertions
        assert result["total"] == 2
        assert len(result["items"]) == 1
        assert result["page"] == 1
        assert result["page_size"] == 1


class TestGetPurchaseDetail:
    """Test cases for get_purchase_detail endpoint"""

    def test_get_purchase_detail_success(self, mock_db_session, mock_inventory_item, mock_partner):
        """Test successful retrieval of purchase detail"""
        # Mock the status attribute to return a proper value
        mock_inventory_item.status = StockStatusEnum.PENDING.value
        
        # Setup inventory query
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = mock_inventory_item
        
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                return MagicMock(return_value=inv_query)
            else:
                # For partner query, return mock_partner
                partner_query = MagicMock()
                partner_query.filter.return_value.first.return_value = mock_partner
                return MagicMock(return_value=partner_query)
        
        mock_db_session.query.side_effect = get_query_side_effect
        
        # Setup partner query
        partner_query = MagicMock()
        partner_query.filter.return_value.first.return_value = mock_partner
        mock_db_session.query.side_effect = [inv_query, partner_query]
        
        # Execute
        result = get_purchase_detail(inv_id=1, db=mock_db_session)
        
        # Assertions
        assert result["code"] == 200
        assert result["msg"] == "success"
        assert result["data"]["id"] == mock_inventory_item.id
        assert result["data"]["order_sn"] == "IN-1"
        assert result["data"]["category"] == 1
        
        assert result["data"]["status"] == StockStatusEnum.PENDING.value
        assert result["data"]["partner_name"] == "Tech Supplier Co."
        assert result["data"]["total_amount"] == 100.0
        
        # Check device list
        assert len(result["data"]["items"]) == 1
        assert result["data"]["items"][0]["model_name"] == "iPhone 13"
        assert result["data"]["items"][0]["devices"][0]["imei"] == "IMEI1234567890"

    def test_get_purchase_detail_not_found(self, mock_db_session):
        """Test purchase detail retrieval when order doesn't exist"""
        from fastapi import HTTPException
        
        # Setup inventory query to return None
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = inv_query
        
        # Execute and expect exception
        with pytest.raises(HTTPException) as exc_info:
            get_purchase_detail(inv_id=999, db=mock_db_session)
        
        assert exc_info.value.status_code == 404
        assert "找不到該進貨單據" in str(exc_info.value.detail)

    def test_get_purchase_detail_no_supplier(self, mock_db_session, mock_inventory_item):
        """Test purchase detail when supplier is not found"""
        # Setup inventory query
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = mock_inventory_item
        
        # Track query calls to return appropriate mocks
        query_call_count = [0]
        def get_query_side_effect(*args, **kwargs):
            if query_call_count[0] == 0:
                query_call_count[0] += 1
                return MagicMock(return_value=inv_query)
            else:
                # For partner query, return None (no supplier)
                partner_query = MagicMock()
                partner_query.filter.return_value.first.return_value = None
                return MagicMock(return_value=partner_query)
        
        mock_db_session.query.side_effect = get_query_side_effect
        
        # Setup partner query to return None
        partner_query = MagicMock()
        partner_query.filter.return_value.first.return_value = None
        mock_db_session.query.side_effect = [inv_query, partner_query]
        
        # Execute
        result = get_purchase_detail(inv_id=1, db=mock_db_session)
        
        # Assertions - should use default values when supplier not found
        assert result["code"] == 200
        assert result["data"]["partner_name"] == "未知供應商"
        assert result["data"]["partner_phone"] == "-"


class TestConfirmInbound:
    """Test cases for confirm_inbound endpoint"""

    def test_confirm_inbound_success(self, mock_db_session, mock_inventory_item):
        """Test successful inbound confirmation"""
        # Mock the status attribute to return a proper value (should be PENDING before confirmation)
        mock_inventory_item.status = StockStatusEnum.PENDING.value
        
        # Setup inventory query
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = mock_inventory_item
        
        # Setup query to return inventory item directly
        inv_query_mock = MagicMock()
        inv_query_mock.filter.return_value.first.return_value = mock_inventory_item
        mock_db_session.query.return_value = inv_query_mock
        
        # Execute
        result = confirm_inbound(
            req=MagicMock(id=mock_inventory_item.id),
            db=mock_db_session
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["msg"] == "確認入庫成功"
        assert str(result["data"]["id"]) == str(mock_inventory_item.id)
        assert result["data"]["status"] == StockStatusEnum.IN_STOCK.value
        
        # Verify inventory item was updated
        assert mock_inventory_item.status == StockStatusEnum.IN_STOCK.value
        assert mock_inventory_item.updated_at is not None
        
        # Verify database operations
        mock_db_session.commit.assert_called_once()
        mock_db_session.rollback.assert_not_called()

    def test_confirm_inbound_order_not_found(self, mock_db_session):
        """Test inbound confirmation when order doesn't exist"""
        # Setup inventory query to return None
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = inv_query
        
        # Execute
        result = confirm_inbound(
            req=MagicMock(id=999),
            db=mock_db_session
        )
        
        # Assertions
        assert result["code"] == 404
        assert result["msg"] == "單據不存在"

    def test_confirm_inbound_already_completed(self, mock_db_session):
        """Test inbound confirmation when order is already completed"""
        # Create inventory item with completed status
        inv = MagicMock(spec=InventoryModel)
        inv.id = 1
        inv.status = StockStatusEnum.IN_STOCK.value
        
        # Setup inventory query
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = inv
        mock_db_session.query.return_value = inv_query
        
        # Execute
        result = confirm_inbound(
            req=MagicMock(id=1),
            db=mock_db_session
        )
        
        # Assertions
        assert result["code"] == 400
        assert result["msg"] == "該單據已完成入庫，請勿重複操作"

    def test_confirm_inbound_database_exception(self, mock_db_session, mock_inventory_item):
        """Test inbound confirmation with database exception"""
        from fastapi import HTTPException
        
        # Setup inventory query
        inv_query = MagicMock()
        inv_query.filter.return_value.first.return_value = mock_inventory_item
        mock_db_session.query.return_value = inv_query
        
        # Simulate database exception
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Mock the status attribute to return a proper value
        mock_inventory_item.status = StockStatusEnum.PENDING.value
        
        # Execute and expect exception
        with pytest.raises(HTTPException) as exc_info:
            confirm_inbound(
                req=MagicMock(id=mock_inventory_item.id),
                db=mock_db_session
            )
        
        assert exc_info.value.status_code == 500
        assert "入庫失敗" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_called_once()
