"""
Unit tests for auth_api.py
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta, timezone
import jwt

# Test imports and setup
pytestmark = pytest.mark.asyncio


class TestCreateAccessToken:
    """Test create_access_token function"""
    
    def test_create_access_token_success(self):
        """Test that access token is created successfully"""
        from src.api.auth_api import create_access_token
        from src.config.config import settings
        from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
        
        data = {"sub": "123", "openid": "test_openid"}
        token = create_access_token(data)
        
        # Verify token is not empty
        assert token
        assert isinstance(token, str)
        
        # Verify token can be decoded
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "123"
        assert payload["openid"] == "test_openid"
        
        # Verify expiration is set
        assert "exp" in payload
        expire_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        expected_expire = now + timedelta(hours=TOKEN_EXPIRE_HOURS)
        # Allow small time difference for test execution
        assert abs((expire_time - expected_expire).total_seconds()) < 2
    
    def test_create_access_token_with_extra_data(self):
        """Test that extra data is preserved in token"""
        from src.api.auth_api import create_access_token
        from src.config.config import settings
        from src.common.constants import JWT_ALGORITHM
        
        data = {"sub": "456", "openid": "another_openid", "custom_field": "value"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "456"
        assert payload["openid"] == "another_openid"
        assert payload["custom_field"] == "value"


class TestGetCurrentUser:
    """Test get_current_user dependency"""
    
    async def test_get_current_user_success(self):
        """Test successful user retrieval"""
        from src.api.auth_api import get_current_user
        from src.model.user_model import UserModel
        from src.config.config import settings
        from src.common.constants import JWT_ALGORITHM
        
        # Create mock user
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.openid = "test_openid"
        
        # Create valid token
        token_data = {"sub": "123"}
        token = jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            # Setup mocks
            mock_decode.return_value = {"sub": "123"}
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
            mock_get_db.return_value = mock_db
            
            # Create mock credentials
            mock_credentials = AsyncMock()
            mock_credentials.credentials = token
            
            with patch('src.api.auth_api.HTTPBearer') as mock_bearer:
                mock_bearer.return_value = lambda: mock_credentials
                result = await get_current_user(db=mock_db)
            
            assert result == mock_user
            mock_decode.assert_called_once_with(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    
    async def test_get_current_user_invalid_token(self):
        """Test with invalid token"""
        from src.api.auth_api import get_current_user
        from fastapi import HTTPException
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid.token.here"
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.PyJWTError("Invalid token")
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=mock_credentials, db=MagicMock())
            
            assert exc_info.value.status_code == 401
    
    async def test_get_current_user_missing_sub(self):
        """Test with token missing sub claim"""
        from src.api.auth_api import get_current_user
        from fastapi import HTTPException
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "test.token"
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode:
            mock_decode.return_value = {"not_sub": "123"}
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=mock_credentials, db=MagicMock())
            
            assert exc_info.value.status_code == 401
    
    async def test_get_current_user_not_found(self):
        """Test when user is not found in database"""
        from src.api.auth_api import get_current_user
        from fastapi import HTTPException
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "test.token"
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            mock_decode.return_value = {"sub": "999"}
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=mock_credentials, db=mock_db)
            
            assert exc_info.value.status_code == 401


class TestGetCurrentStaff:
    """Test get_current_staff dependency"""
    
    async def test_get_current_staff_success(self):
        """Test successful staff retrieval"""
        from src.api.auth_api import get_current_staff
        from src.model.staff_model import StaffModel
        
        # Create mock user and staff
        mock_user = MagicMock()
        mock_user.id = 123
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.id = 456
        mock_staff.shop_id = 789
        mock_staff.user_id = 123
        mock_staff.status = 1  # Active
        
        with patch('src.api.auth_api.get_current_user') as mock_get_user, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            mock_get_user.return_value = mock_user
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            result = await get_current_staff(x_shop_id=789, current_user=mock_user, db=mock_db)
            
            assert result == mock_staff
    
    async def test_get_current_staff_missing_shop_id(self):
        """Test when X-Shop-Id header is missing"""
        from src.api.auth_api import get_current_staff
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_staff(x_shop_id=None, current_user=MagicMock(), db=MagicMock())
        
        assert exc_info.value.status_code == 400
    
    async def test_get_current_staff_not_found(self):
        """Test when staff is not found"""
        from src.api.auth_api import get_current_staff
        from fastapi import HTTPException
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_staff(x_shop_id=789, current_user=mock_user, db=mock_db)
            
            assert exc_info.value.status_code == 403
    
    async def test_get_current_staff_disabled(self):
        """Test when staff is disabled"""
        from src.api.auth_api import get_current_staff
        from fastapi import HTTPException
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.status = 2  # Disabled
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_staff(x_shop_id=789, current_user=mock_user, db=mock_db)
            
            assert exc_info.value.status_code == 401
    
    async def test_get_current_staff_pending(self):
        """Test when staff is pending activation"""
        from src.api.auth_api import get_current_staff
        from fastapi import HTTPException
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.status = 0  # Pending
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_staff(x_shop_id=789, current_user=mock_user, db=mock_db)
            
            assert exc_info.value.status_code == 403


class TestAllowShopManager:
    """Test allow_shop_manager dependency"""
    
    async def test_allow_shop_manager_success(self):
        """Test successful manager check"""
        from src.api.auth_api import allow_shop_manager
        from src.model.staff_model import StaffModel
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.role = "owner"
        
        with patch('src.api.auth_api.get_current_staff') as mock_get_staff:
            mock_get_staff.return_value = mock_staff
            
            result = await allow_shop_manager(current_staff=mock_staff)
            assert result == mock_staff
    
    async def test_allow_shop_manager_forbidden(self):
        """Test when user is not a manager"""
        from src.api.auth_api import allow_shop_manager
        from fastapi import HTTPException
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.role = "staff"
        
        with patch('src.api.auth_api.get_current_staff') as mock_get_staff:
            mock_get_staff.return_value = mock_staff
            
            with pytest.raises(HTTPException) as exc_info:
                await allow_shop_manager(current_staff=mock_staff)
            
            assert exc_info.value.status_code == 403


class TestWxLogin:
    """Test wx_login endpoint"""
    
    async def test_wx_login_success_new_user(self):
        """Test successful login for new user"""
        from src.api.auth_api import wx_login
        from src.model.user_model import UserModel
        from src.model.staff_model import StaffModel
        
        payload = {"code": "test_code_123"}
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            # Mock HTTPX client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"openid": "test_openid_123", "errcode": 0}
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            
            # Mock database
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            result = await wx_login(payload, db=mock_db)
            
            assert result.token
            assert result.user_info.id
            assert result.user_info.nickname
    
    async def test_wx_login_empty_code(self):
        """Test with empty code"""
        from src.api.auth_api import wx_login
        from src.common.exceptions import BusinessException
        
        payload = {"code": ""}
        
        with pytest.raises(BusinessException) as exc_info:
            await wx_login(payload, db=MagicMock())
        
        assert exc_info.value.status_code == 400
    
    async def test_wx_login_weixin_error(self):
        """Test when Weixin API returns error"""
        from src.api.auth_api import wx_login
        from src.common.exceptions import BusinessException
        
        payload = {"code": "test_code"}
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"errcode": 40029, "errmsg": "code invalid"}
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            
            with pytest.raises(BusinessException) as exc_info:
                await wx_login(payload, db=MagicMock())
            
            assert exc_info.value.status_code == 400
    
    async def test_wx_login_missing_openid(self):
        """Test when Weixin API doesn't return openid"""
        from src.api.auth_api import wx_login
        from src.common.exceptions import BusinessException
        
        payload = {"code": "test_code"}
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"errcode": 0}  # Success but no openid
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            
            with pytest.raises(BusinessException) as exc_info:
                await wx_login(payload, db=MagicMock())
            
            assert exc_info.value.status_code == 400
    
    async def test_wx_login_existing_user(self):
        """Test successful login for existing user"""
        from src.api.auth_api import wx_login
        from src.model.user_model import UserModel
        from src.model.staff_model import StaffModel
        
        payload = {"code": "test_code_123"}
        
        # Create mock user and staff
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.openid = "test_openid_123"
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.id = 456
        mock_staff.user_id = 123
        mock_staff.shop_id = 789
        mock_staff.status = 1
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            # Mock HTTPX client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.json.return_value = {"openid": "test_openid_123", "errcode": 0}
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            
            # Mock database - user exists
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_user,  # First call for user lookup
                mock_staff   # Second call for staff lookup
            ]
            mock_get_db.return_value = mock_db
            
            result = await wx_login(payload, db=mock_db)
            
            assert result.token
            assert result.user_info.id == 456  # Staff ID


class TestGetMyInfo:
    """Test get_my_info endpoint"""
    
    async def test_get_my_info_success(self):
        """Test successful info retrieval"""
        from src.api.auth_api import get_my_info
        from src.model.user_model import UserModel
        from src.model.staff_model import StaffModel
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.id = 456
        mock_staff.shop_id = 789
        mock_staff.user_id = 123
        mock_staff.name = "Test User"
        mock_staff.role = "staff"
        mock_staff.status = 1
        
        with patch('src.api.auth_api.get_current_user') as mock_get_user, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            mock_get_user.return_value = mock_user
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            result = await get_my_info(x_shop_id=789, db=mock_db, current_user=mock_user)
            
            assert result.id == 456
            assert result.nickname == "Test User"
            assert result.role == "staff"
    
    async def test_get_my_info_not_found(self):
        """Test when staff profile not found"""
        from src.api.auth_api import get_my_info
        from src.common.exceptions import BusinessException
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(BusinessException) as exc_info:
                await get_my_info(x_shop_id=789, db=mock_db, current_user=mock_user)
            
            assert exc_info.value.status_code == 403
    
    async def test_get_my_info_inactive_staff(self):
        """Test when staff is inactive"""
        from src.api.auth_api import get_my_info
        from src.common.exceptions import BusinessException
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        
        # First query returns None (active staff), second returns inactive
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                None,  # Active staff not found
                MagicMock(status=0)  # Inactive staff found for debugging
            ]
            mock_get_db.return_value = mock_db
            
            with pytest.raises(BusinessException) as exc_info:
                await get_my_info(x_shop_id=789, db=mock_db, current_user=mock_user)
            
            assert exc_info.value.status_code == 403


class TestUpdateMyInfo:
    """Test update_my_info endpoint"""
    
    async def test_update_my_info_success(self):
        """Test successful info update"""
        from src.api.auth_api import update_my_info
        from src.model.user_model import UserModel
        from src.model.staff_model import StaffModel
        
        user_data = {"nickname": "New Name", "phone": "1234567890"}
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.phone = "old_phone"
        
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.id = 456
        mock_staff.user_id = 123
        mock_staff.shop_id = 789
        mock_staff.name = "Old Name"
        mock_staff.status = 1
        
        with patch('src.api.auth_api.get_current_user') as mock_get_user, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            mock_get_user.return_value = mock_user
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            result = await update_my_info(
                user_in=user_data,
                x_shop_id=789,
                current_user=mock_user,
                db=mock_db
            )
            
            assert result.nickname == "New Name"
    
    async def test_update_my_info_no_fields(self):
        """Test with no update fields provided"""
        from src.api.auth_api import update_my_info
        from src.common.exceptions import BusinessException
        
        user_data = {}
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        
        with pytest.raises(BusinessException) as exc_info:
            await update_my_info(
                user_in=user_data,
                x_shop_id=789,
                current_user=mock_user,
                db=MagicMock()
            )
        
        assert exc_info.value.status_code == 400
    
    async def test_update_my_info_invalid_default_shop(self):
        """Test with invalid default shop"""
        from src.api.auth_api import update_my_info
        from src.common.exceptions import BusinessException
        
        user_data = {"default_shop_id": 999}
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(BusinessException) as exc_info:
                await update_my_info(
                    user_in=user_data,
                    x_shop_id=789,
                    current_user=mock_user,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 400


class TestPermissionChecker:
    """Test PermissionChecker class"""
    
    async def test_permission_checker_allowed(self):
        """Test when user has required role"""
        from src.api.auth_api import PermissionChecker
        from src.model.user_model import UserModel
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.role = "admin"
        
        checker = PermissionChecker(allowed_roles=["admin", "manager"])
        
        with patch('src.api.auth_api.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            result = await checker(current_user=mock_user)
            assert result == mock_user
    
    async def test_permission_checker_forbidden(self):
        """Test when user doesn't have required role"""
        mock_user = MagicMock()
        mock_user.role = UserRole.STAFF
        
        with patch('src.api.auth_api.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            checker = PermissionChecker([UserRole.MANAGER])
            
            with pytest.raises(HTTPException) as exc_info:
                await checker.__call__(None)
            
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        from src.api.auth_api import PermissionChecker
        from fastapi import HTTPException
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.role = "staff"
        
        checker = PermissionChecker(allowed_roles=["admin", "manager"])
        
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=mock_user)
        
        assert exc_info.value.status_code == 403
