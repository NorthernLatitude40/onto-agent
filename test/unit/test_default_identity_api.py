"""
Unit tests for default_identity_api.py endpoints
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from src.api.v1.endpoints.default_identity_api import set_default_identity
from src.model.staff_model import StaffModel
from src.model.user_model import UserModel
from src.model.clark_schema import SetDefaultIdentitySchema, SetDefaultIdentityResponse
from src.common.exceptions import BusinessException


@pytest.fixture
def anyio_backend():
    # 只跑 asyncio，不跑 trio
    return "asyncio"


def make_user(user_id=1):
    """Create a mock user for testing"""
    user = MagicMock(spec=UserModel)
    user.id = user_id
    user.default_shop_id = None
    user.default_staff_id = None
    return user


def make_staff(staff_id=1, user_id=1, shop_id=1, status=1):
    """Create a mock staff for testing"""
    staff = MagicMock(spec=StaffModel)
    staff.id = staff_id
    staff.user_id = user_id
    staff.shop_id = shop_id
    staff.status = status
    return staff


class TestSetDefaultIdentity:
    """Test cases for set_default_identity endpoint"""

    def test_set_default_identity_success(self):
        """Test successful setting of default identity"""
        db = MagicMock(spec=Session)
        
        # Setup mock data
        current_user = make_user(1)
        staff = make_staff(26, user_id=1, shop_id=1, status=1)
        
        # Configure database mock to return the staff
        db.query().filter().first.return_value = staff
        
        # Create request payload
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=26
        )
        
        # Call the endpoint
        result = set_default_identity(
            payload=payload,
            db=db,
            current_user=current_user
        )
        
        # Verify database operations
        assert db.query().filter().first.called
        assert db.add.call_count == 1
        assert db.commit.call_count == 1
        
        # Verify user fields were updated
        assert current_user.default_shop_id == 1
        assert current_user.default_staff_id == 26
        
        # Verify response structure
        assert isinstance(result, SetDefaultIdentityResponse)
        assert result.code == 200
        assert result.message == "默认身份设置成功"

    def test_set_default_identity_invalid_staff(self):
        """Test when staff doesn't exist or doesn't belong to user"""
        db = MagicMock(spec=Session)
        
        # Setup mock data - staff doesn't match criteria
        current_user = make_user(1)
        db.query().filter().first.return_value = None  # No matching staff found
        
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=999  # Non-existent staff ID
        )
        
        # Should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            set_default_identity(
                payload=payload,
                db=db,
                current_user=current_user
            )
        
        # Verify exception details
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "INVALID_STAFF_IDENTITY"
        assert "指定的店铺身份无效或不属于当前用户" in exc_info.value.detail
        
        # Verify no database changes were made
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_set_default_identity_wrong_user(self):
        """Test when staff belongs to different user"""
        db = MagicMock(spec=Session)
        
        # Setup mock data - staff belongs to different user
        current_user = make_user(1)
        # The query should return None because user_id doesn't match
        db.query().filter().first.return_value = None
        
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=26
        )
        
        # Should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            set_default_identity(
                payload=payload,
                db=db,
                current_user=current_user
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "INVALID_STAFF_IDENTITY"

    def test_set_default_identity_wrong_shop(self):
        """Test when staff belongs to different shop"""
        db = MagicMock(spec=Session)
        
        # Setup mock data - staff belongs to different shop
        current_user = make_user(1)
        # The query should return None because shop_id doesn't match
        db.query().filter().first.return_value = None
        
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=26
        )
        
        # Should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            set_default_identity(
                payload=payload,
                db=db,
                current_user=current_user
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "INVALID_STAFF_IDENTITY"

    def test_set_default_identity_inactive_staff(self):
        """Test when staff is not active (status != 1)"""
        db = MagicMock(spec=Session)
        
        # Setup mock data - inactive staff
        current_user = make_user(1)
        # The query should return None because status doesn't match
        db.query().filter().first.return_value = None
        
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=26
        )
        
        # Should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            set_default_identity(
                payload=payload,
                db=db,
                current_user=current_user
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "INVALID_STAFF_IDENTITY"

    def test_set_default_identity_database_error(self):
        """Test when database update fails"""
        db = MagicMock(spec=Session)
        
        # Setup mock data
        current_user = make_user(1)
        staff = make_staff(26, user_id=1, shop_id=1, status=1)
        db.query().filter().first.return_value = staff
        
        # Make commit raise an exception
        db.add.side_effect = Exception("Database connection error")
        
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=26
        )
        
        # Should raise BusinessException with 500 status
        with pytest.raises(BusinessException) as exc_info:
            set_default_identity(
                payload=payload,
                db=db,
                current_user=current_user
            )
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.code == "DATABASE_UPDATE_FAILED"
        assert "数据库更新失败" in exc_info.value.detail

    def test_set_default_identity_multiple_staff_validation(self):
        """Test that all validation criteria are checked together"""
        db = MagicMock(spec=Session)
        
        # Setup mock data - staff fails multiple criteria
        current_user = make_user(1)
        # The query should return None because none of the criteria match
        db.query().filter().first.return_value = None
        
        payload = SetDefaultIdentitySchema(
            default_shop_id=1,
            default_staff_id=26
        )
        
        # Should raise BusinessException
        with pytest.raises(BusinessException) as exc_info:
            set_default_identity(
                payload=payload,
                db=db,
                current_user=current_user
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.code == "INVALID_STAFF_IDENTITY"
