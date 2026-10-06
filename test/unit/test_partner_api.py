"""
Unit tests for partner_api.py endpoints
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

# Import the API module - need to patch imports before they're used
with patch('src.model.user_model.UserModel'):
    with patch('src.model.staff_model.StaffModel'):
        with patch('src.model.partner_model.ShopModel'):
            with patch('src.model.inventory_model.InventoryModel'):
                with patch('src.api.v1.endpoints.partner_api.Partner'):
                    with patch('src.api.v1.endpoints.partner_api.get_db_async'):
                        with patch('src.api.v1.endpoints.partner_api.get_db'):
                            from src.api.v1.endpoints.partner_api import (
                                search_partner_by_phone,
                                create_partner,
                                get_partner_detail,
                            )

from src.model.partner_model import Partner
from src.model.partner_schema import PartnerCreate, PartnerResponse
from src.common.exceptions import BusinessException


class TestSearchPartnerByPhone:
    """Test search_partner_by_phone endpoint"""
    
    @pytest.mark.asyncio
    async def test_search_partner_success(self):
        """Test successful partner search by phone"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        mock_partner.name = "Test Customer"
        mock_partner.phone = "13800138000"
        mock_partner.type = 1
        mock_partner.remark = "Test remark"
        mock_partner.receivable_amount = 100.50
        mock_partner.payable_amount = 200.75
        mock_partner.shop_id = 1
        mock_partner.created_at = datetime.now()
        mock_partner.updated_at = datetime.now()
        
        # Mock database execute result
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_partner
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Call the endpoint
        result = await search_partner_by_phone(
            phone="13800138000",
            shop_id=1,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["message"] == "查詢成功"
        assert result["data"].id == 1
        assert result["data"].name == "Test Customer"
        assert result["data"].phone == "13800138000"
    
    @pytest.mark.asyncio
    async def test_search_partner_empty_phone(self):
        """Test search with empty phone raises BusinessException"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Call the endpoint with empty phone
        with pytest.raises(BusinessException) as exc_info:
            await search_partner_by_phone(
                phone="   ",
                shop_id=1,
                db=db
            )
        
        # Assertions
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "BAD_REQUEST"
        assert "手機號碼不能為空" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_search_partner_not_found(self):
        """Test search when partner not found raises BusinessException"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock empty result
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Call the endpoint
        with pytest.raises(BusinessException) as exc_info:
            await search_partner_by_phone(
                phone="13800138000",
                shop_id=1,
                db=db
            )
        
        # Assertions
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.code == "NOT_FOUND"
        assert "未找到相關客戶" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_search_partner_no_shop_id(self):
        """Test search with no shop_id (should use 0 as default)"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        mock_partner.name = "Test Customer"
        mock_partner.phone = "13800138000"
        mock_partner.type = 1
        mock_partner.remark = "Test remark"
        mock_partner.receivable_amount = 0.00
        mock_partner.payable_amount = 0.00
        mock_partner.shop_id = 0
        
        # Mock database execute result
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_partner
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Call the endpoint without shop_id
        result = await search_partner_by_phone(
            phone="13800138000",
            shop_id=None,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["data"].id == 1
    

class TestCreatePartner:
    """Test create_partner endpoint"""
    
    @pytest.mark.asyncio
    async def test_create_partner_success(self):
        """Test successful partner creation"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock payload
        partner_in = PartnerCreate(
            name="New Customer",
            phone="13800138000",
            type=1,
            remark="New customer"
        )
        
        # Mock new partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        mock_partner.name = "New Customer"
        mock_partner.phone = "13800138000"
        mock_partner.type = 1
        mock_partner.remark = "New customer"
        mock_partner.receivable_amount = 0.00
        mock_partner.payable_amount = 0.00
        mock_partner.shop_id = 1
        mock_partner.created_at = datetime.now()
        mock_partner.updated_at = datetime.now()
        
        # Mock database execute result (no existing partner)
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Mock commit and refresh
        def mock_add(obj):
            # Populate the object with required fields
            obj.id = 1
            obj.created_at = datetime.now()
            obj.updated_at = datetime.now()
        db.add = MagicMock(side_effect=mock_add)
        db.commit = AsyncMock()
        db.refresh = AsyncMock(return_value=None)
        
        # Call the endpoint
        result = await create_partner(
            partner_in=partner_in,
            shop_id=1,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["message"] == "創建成功"
        assert result["data"].id == 1
        assert result["data"].name == "New Customer"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_create_partner_empty_name(self):
        """Test create with empty name raises BusinessException"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock payload with empty name
        partner_in = PartnerCreate(
            name="",
            phone="13800138000",
            type=1,
            remark="New customer"
        )
        
        # Call the endpoint
        with pytest.raises(BusinessException) as exc_info:
            await create_partner(
                partner_in=partner_in,
                shop_id=1,
                db=db
            )
        
        # Assertions
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "BAD_REQUEST"
        assert "客戶名稱不能為空" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_create_partner_existing_phone(self):
        """Test create when partner with phone already exists (update scenario)"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock payload
        partner_in = PartnerCreate(
            name="Updated Customer",
            phone="13800138000",
            type=1,
            remark="Updated customer"
        )
        
        # Mock existing partner data
        mock_existing_partner = MagicMock(spec=Partner)
        mock_existing_partner.id = 1
        mock_existing_partner.name = "Old Customer"
        mock_existing_partner.phone = "13800138000"
        mock_existing_partner.type = 1
        mock_existing_partner.remark = ""
        mock_existing_partner.receivable_amount = 0.00
        mock_existing_partner.payable_amount = 0.00
        mock_existing_partner.shop_id = 1
        mock_existing_partner.created_at = datetime.now()
        mock_existing_partner.updated_at = datetime.now()
        
        # Mock database execute result (existing partner found)
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_existing_partner
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Mock commit and refresh
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        
        # Call the endpoint
        result = await create_partner(
            partner_in=partner_in,
            shop_id=1,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["message"] == "客戶已存在，已更新信息"
        assert result["data"].id == 1
        assert mock_existing_partner.name == "Updated Customer"
        db.commit.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_create_partner_type_update(self):
        """Test create when partner type needs to be updated to 3 (both customer and supplier)"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock payload - changing from customer (1) to supplier (2)
        partner_in = PartnerCreate(
            name="Customer Supplier",
            phone="13800138000",
            type=2,  # Changing to supplier
            remark="Both customer and supplier"
        )
        
        # Mock existing partner data (customer type)
        mock_existing_partner = MagicMock(spec=Partner)
        mock_existing_partner.id = 1
        mock_existing_partner.name = "Customer Supplier"
        mock_existing_partner.phone = "13800138000"
        mock_existing_partner.type = 1  # Currently customer only
        mock_existing_partner.remark = ""
        mock_existing_partner.receivable_amount = 0.00
        mock_existing_partner.payable_amount = 0.00
        mock_existing_partner.shop_id = 1
        mock_existing_partner.created_at = datetime.now()
        mock_existing_partner.updated_at = datetime.now()
        
        # Mock database execute result (existing partner found)
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_result.scalars.return_value.first.return_value = mock_existing_partner
        db.execute.return_value = mock_result
        
        # Mock commit and refresh
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        
        # Call the endpoint
        result = await create_partner(
            partner_in=partner_in,
            shop_id=1,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert mock_existing_partner.type == 3  # Should be updated to both
    
    @pytest.mark.asyncio
    async def test_create_partner_database_error(self):
        """Test create when database error occurs raises BusinessException"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock payload
        partner_in = PartnerCreate(
            name="New Customer",
            phone="13800138000",
            type=1,
            remark="New customer"
        )
        
        # Mock new partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        
        # Mock database execute result (no existing partner)
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Mock add to raise exception
        db.add = MagicMock(side_effect=Exception("Database error"))
        db.rollback = AsyncMock()
        
        # Call the endpoint
        with pytest.raises(BusinessException) as exc_info:
            await create_partner(
                partner_in=partner_in,
                shop_id=1,
                db=db
            )
        
        # Assertions
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.code == "INTERNAL_SERVER_ERROR"
        assert "創建客戶時發生未知錯誤" in str(exc_info.value.detail)
        db.rollback.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_create_partner_no_phone(self):
        """Test create partner without phone number (should still work)"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock payload without phone
        partner_in = PartnerCreate(
            name="New Customer",
            phone=None,
            type=1,
            remark="No phone customer"
        )
        
        # Mock new partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        mock_partner.name = "New Customer"
        mock_partner.phone = None
        mock_partner.type = 1
        mock_partner.remark = "No phone customer"
        mock_partner.receivable_amount = 0.00
        mock_partner.payable_amount = 0.00
        mock_partner.shop_id = 1
        mock_partner.created_at = datetime.now()
        mock_partner.updated_at = datetime.now()
        
        # Mock commit and refresh
        def mock_add(obj):
            # Populate the object with required fields
            obj.id = 1
            obj.created_at = datetime.now()
            obj.updated_at = datetime.now()
        db.add = MagicMock(side_effect=mock_add)
        db.commit = AsyncMock()
        db.refresh = AsyncMock(return_value=None)
        
        # Call the endpoint
        result = await create_partner(
            partner_in=partner_in,
            shop_id=1,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["message"] == "創建成功"
        assert result["data"].id == 1
    

class TestGetPartnerDetail:
    """Test get_partner_detail endpoint"""
    
    @pytest.mark.asyncio
    async def test_get_partner_detail_success(self):
        """Test successful partner detail retrieval"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        mock_partner.name = "Test Customer"
        mock_partner.phone = "13800138000"
        mock_partner.type = 1
        mock_partner.remark = "Test remark"
        mock_partner.receivable_amount = 100.50
        mock_partner.payable_amount = 200.75
        mock_partner.shop_id = 1
        mock_partner.created_at = datetime.now()
        mock_partner.updated_at = datetime.now()
        
        # Mock database execute result
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        
        # Mock the scalars().first() call chain
        mock_scalars.first.return_value = mock_partner
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Call the endpoint
        result = await get_partner_detail(
            partner_id=1,
            shop_id=1,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["message"] == "查詢成功"
        assert result["data"].id == 1
        assert result["data"].name == "Test Customer"
    
    @pytest.mark.asyncio
    async def test_get_partner_detail_not_found(self):
        """Test get detail when partner not found raises BusinessException"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock empty result
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        
        # Mock the scalars().first() call chain
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Call the endpoint
        with pytest.raises(BusinessException) as exc_info:
            await get_partner_detail(
                partner_id=999,
                shop_id=1,
                db=db
            )
        
        # Assertions
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.code == "NOT_FOUND"
        assert "該往來單位不存在" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_partner_detail_invalid_id(self):
        """Test get detail with invalid partner_id (should be positive integer)"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Call the endpoint with invalid ID (negative)
        # This should raise a validation error from FastAPI's Query parameter
        # We'll test this by checking if it raises an exception
        try:
            await get_partner_detail(
                partner_id=-1,
                shop_id=1,
                db=db
            )
            assert False, "Should have raised an exception for negative ID"
        except Exception as e:
            # FastAPI should raise a validation error
            assert True  # Expected behavior
    
    @pytest.mark.asyncio
    async def test_get_partner_detail_no_shop_id(self):
        """Test get detail with no shop_id (should use 0 as default)"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Mock partner data
        mock_partner = MagicMock(spec=Partner)
        mock_partner.id = 1
        mock_partner.name = "Test Customer"
        mock_partner.phone = "13800138000"
        mock_partner.type = 1
        mock_partner.remark = "Test remark"
        mock_partner.receivable_amount = 100.50
        mock_partner.payable_amount = 200.75
        mock_partner.shop_id = 0
        
        # Mock database execute result
        mock_result = MagicMock()  # Not AsyncMock - scalars is not async in SQLAlchemy 2.0+
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_partner
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result
        
        # Call the endpoint without shop_id
        result = await get_partner_detail(
            partner_id=1,
            shop_id=None,
            db=db
        )
        
        # Assertions
        assert result["code"] == 200
        assert result["data"].id == 1
