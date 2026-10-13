"""
Unit tests for shop_api.py endpoints
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Import the API module - need to patch imports before they're used
with patch('src.api.v1.endpoints.shop_api.ShopModel'):
    with patch('src.api.v1.endpoints.shop_api.StaffModel'):
        from src.api.v1.endpoints.shop_api import (
            create_shop,
            delete_shop,
            update_shop_info,
            get_current_shop_info,
            get_my_shops
        )

from src.model.shop_model import ShopModel
from src.model.staff_model import StaffModel
from src.model.user_model import UserModel
from src.model.shop_schema import CreateShopPayload, UpdateShopPayload
from src.common.dict import ShopRole
from src.common.exceptions import BusinessException


class TestCreateShop:
    """Test create_shop endpoint"""
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_create_shop_success(self, mock_get_current_user):
        """Test successful shop creation"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_user.nickname = "Test User"
        mock_user.phone = "13800000000"
        mock_user.avatar = "https://example.com/avatar.jpg"
        mock_get_current_user.return_value = mock_user
        
        # Mock payload
        payload = CreateShopPayload(
            name="Test Shop",
            logo="https://example.com/logo.png",
            contact_name="Store Manager",
            contact_phone="13800000001",
            province="广东省",
            city="深圳市",
            district="南山区",
            address_detail="科技园路1号"
        )
        
        # Mock new shop
        new_shop = MagicMock(spec=ShopModel)
        new_shop.id = 1
        new_shop.name = "Test Shop"
        new_shop.logo = "https://example.com/logo.png"
        new_shop.contact_name = "Store Manager"
        new_shop.contact_phone = "13800000001"
        new_shop.province = "广东省"
        new_shop.city = "深圳市"
        new_shop.district = "南山区"
        new_shop.address_detail = "科技园路1号"
        new_shop.is_active = True
        
        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.return_value = None
        
        # Test the function
        result = create_shop(payload=payload, db=db, current_user=mock_user)
        
        # Assertions
        assert result == new_shop
        db.add.assert_called()
        db.flush.assert_called()
        db.commit.assert_called()
        db.refresh.assert_called_with(new_shop)
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_create_shop_failure(self, mock_get_current_user):
        """Test shop creation failure with exception"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # Mock payload
        payload = CreateShopPayload(
            name="Test Shop",
            logo="https://example.com/logo.png",
            contact_name="Store Manager",
            contact_phone="13800000001",
            province="广东省",
            city="深圳市",
            district="南山区",
            address_detail="科技园路1号"
        )
        
        # Make db.add raise an exception
        db.add.side_effect = Exception("Database error")
        
        # Test the function - should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            create_shop(payload=payload, db=db, current_user=mock_user)
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        db.rollback.assert_called()


class TestDeleteShop:
    """Test delete_shop endpoint"""
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_delete_shop_success(self, mock_get_current_user):
        """Test successful shop deletion"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # Mock staff record (owner)
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.user_id = 1
        mock_staff.shop_id = 1
        mock_staff.role = "owner"
        
        # Mock shop
        mock_shop = MagicMock(spec=ShopModel)
        mock_shop.id = 1
        mock_shop.status = 0  # Will be set to 0 (deleted)
        
        db.query.return_value.filter.return_value.first.return_value = mock_staff
        db.query.return_value.filter.return_value.first().__bool__ = True
        db.query.return_value.filter.return_value.first.return_value.id = 1
        
        # Test the function
        result = delete_shop(target_shop_id=1, db=db, current_user=mock_user)
        
        # Assertions
        assert result == {"message": "店铺已成功解散/註銷"}
        mock_shop.status = 0
        db.commit.assert_called()
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_delete_shop_not_owner(self, mock_get_current_user):
        """Test shop deletion by non-owner"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # Mock staff record (not owner)
        mock_staff = None
        db.query.return_value.filter.return_value.first.return_value = None
        
        # Test the function - should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            delete_shop(target_shop_id=1, db=db, current_user=mock_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "權限不足" in str(exc_info.value.detail)


class TestUpdateShopInfo:
    """Test update_shop_info endpoint"""
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_update_shop_info_success(self, mock_get_current_user):
        """Test successful shop info update"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # Mock payload
        payload = UpdateShopPayload(
            name="Updated Shop Name",
            logo="https://example.com/new_logo.png"
        )
        
        # Mock staff record (owner)
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.shop_id = 1
        mock_staff.user_id = 1
        mock_staff.role = "owner"
        mock_staff.status = 1
        
        # Mock shop
        mock_shop = MagicMock(spec=ShopModel)
        mock_shop.id = 1
        mock_shop.name = "Original Name"
        mock_shop.logo = "https://example.com/old_logo.png"
        
        db.query.return_value.filter.return_value.first.return_value = mock_staff
        db.query.return_value.filter.return_value.first().__bool__ = True
        db.query.return_value.filter.return_value.first.return_value.id = 1
        
        # Test the function
        result = update_shop_info(
            payload=payload,
            db=db,
            x_shop_id=1,
            current_user=mock_user
        )
        
        # Assertions
        assert result["code"] == 200
        assert "更新成功" in result["message"]
        db.commit.assert_called()
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_update_shop_info_missing_header(self, mock_get_current_user):
        """Test shop info update with missing X-Shop-Id header"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # Mock payload
        payload = UpdateShopPayload(
            name="Updated Shop Name",
            logo="https://example.com/new_logo.png"
        )
        
        # Test the function - should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            update_shop_info(
                payload=payload,
                db=db,
                x_shop_id=None,  # Missing header
                current_user=mock_user
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "X-Shop-Id" in str(exc_info.value.detail)


class TestGetCurrentShopInfo:
    """Test get_current_shop_info endpoint"""
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_get_current_shop_info_success(self, mock_get_current_user):
        """Test successful shop info retrieval"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # Mock staff record
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.shop_id = 1
        mock_staff.user_id = 1
        mock_staff.status = 1
        
        # Mock shop
        mock_shop = MagicMock(spec=ShopModel)
        mock_shop.id = 1
        mock_shop.name = "Test Shop"
        mock_shop.logo = "https://example.com/logo.png"
        mock_shop.contact_name = "Store Manager"
        mock_shop.contact_phone = "13800000000"
        mock_shop.province = "广东省"
        mock_shop.city = "深圳市"
        mock_shop.district = "南山区"
        mock_shop.address_detail = "科技园路1号"
        mock_shop.is_active = True
        
        db.query.return_value.filter.return_value.first.return_value = mock_staff
        db.query.return_value.filter.return_value.first().__bool__ = True
        db.query.return_value.filter.return_value.first.return_value.id = 1
        
        # Test the function
        result = get_current_shop_info(
            x_shop_id=1,
            db=db,
            current_user=mock_user
        )
        
        # Assertions
        assert result == mock_shop
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_get_current_shop_info_no_staff(self, mock_get_current_user):
        """Test shop info retrieval when user has no staff record"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user
        
        # No staff record found
        db.query.return_value.filter.return_value.first.return_value = None
        
        # Test the function - should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            get_current_shop_info(
                x_shop_id=1,
                db=db,
                current_user=mock_user
            )
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestGetMyShops:
    """Test get_my_shops endpoint"""
    
    @patch('src.api.v1.endpoints.shop_api.get_current_user')
    def test_get_my_shops_success(self, mock_get_current_user):
        """Test successful retrieval of user's shops"""
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock current user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_user.default_shop_id = None
        mock_user.default_staff_id = None
        mock_get_current_user.return_value = mock_user
        
        # Mock shop and staff data
        mock_shop_1 = MagicMock(spec=ShopModel)
        mock_shop_1.id = 1
        mock_shop_1.name = "Shop 1"
        mock_shop_1.logo = "https://example.com/logo1.png"
        mock_shop_1.contact_name = "Manager 1"
        mock_shop_1.contact_phone = "13800000001"
        mock_shop_1.province = "广东省"
        mock_shop_1.city = "深圳市"
        mock_shop_1.district = "南山区"
        mock_shop_1.address_detail = "地址1"
        mock_shop_1.is_active = True
        
        # Test the function
        result = get_my_shops(db=db, current_user=mock_user)
        
        # Assertions - should return a list
        assert isinstance(result, list)
