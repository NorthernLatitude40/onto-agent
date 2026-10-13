"""
Simple unit tests for auth_api.py - testing the core logic without FastAPI dependency injection
"""
# Import models at module level to avoid circular dependency issues
from src.model.user_model import UserModel
from src.model.staff_model import StaffModel
from src.model.shop_model import ShopModel
from src.model.inventory_model import InventoryModel
from src.model.partner_model import Partner
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException, status
import jwt

# Test imports and setup


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
    
        with patch('src.api.auth_api.jwt.decode') as mock_decode:
    
            # Setup mocks
            mock_decode.return_value = {"sub": "123"}
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    
            # Create mock credentials
            mock_credentials = MagicMock()
            mock_credentials.credentials = token

            result = get_current_user(mock_credentials, db=mock_db)

            assert result.id == 123
            assert result.openid == "test_openid"
    
    async def test_get_current_user_invalid_token(self):
        """Test with invalid token"""
        from src.api.auth_api import get_current_user
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid.token.here"
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.PyJWTError("Invalid token")

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, MagicMock())
            
            assert exc_info.value.status_code == 401
    
    async def test_get_current_user_missing_sub(self):
        """Test with token missing sub claim"""
        from src.api.auth_api import get_current_user
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "test.token"
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode:
            mock_decode.return_value = {"not_sub": "123"}

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, MagicMock())
            
            assert exc_info.value.status_code == 401
    
    async def test_get_current_user_not_found(self):
        """Test when user is not found in database"""
        from src.api.auth_api import get_current_user
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "test.token"
        
        with patch('src.api.auth_api.jwt.decode') as mock_decode, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            mock_decode.return_value = {"sub": "999"}
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, mock_db)
            
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
        mock_staff.status = 1
    
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db

            result = get_current_staff(x_shop_id=789, current_user=mock_user, db=mock_db)

            assert result.id == 456
            assert result.shop_id == 789
    
    async def test_get_current_staff_missing_shop_id(self):
        """Test when X-Shop-Id header is missing"""
        from src.api.auth_api import get_current_staff
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_staff(None, MagicMock(), MagicMock())
        
        assert exc_info.value.status_code == 400
    
    async def test_get_current_staff_not_found(self):
        """Test when staff is not found"""
        from src.api.auth_api import get_current_staff
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_staff(789, mock_user, mock_db)
            
            assert exc_info.value.status_code == 403
    
    async def test_get_current_staff_disabled(self):
        """Test when staff is disabled"""
        from src.api.auth_api import get_current_staff
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        mock_staff = MagicMock()
        mock_staff.status = 2  # Disabled
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_staff(789, mock_user, mock_db)
            
            assert exc_info.value.status_code == 401
    
    async def test_get_current_staff_pending(self):
        """Test when staff is pending activation"""
        from src.api.auth_api import get_current_staff
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        mock_staff = MagicMock()
        mock_staff.status = 0  # Pending
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_staff(789, mock_user, mock_db)
            
            assert exc_info.value.status_code == 403


class TestAllowShopManager:
    """Test allow_shop_manager dependency"""
    
    async def test_allow_shop_manager_success(self):
        """Test successful manager check"""
        from src.api.auth_api import allow_shop_manager
        from src.model.staff_model import StaffModel
    
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.role = "manager"
    
        with patch('src.api.auth_api.get_current_staff') as mock_get_staff:
            mock_get_staff.return_value = mock_staff

            result = allow_shop_manager(mock_staff)

            assert result.role == "manager"
    
    async def test_allow_shop_manager_forbidden(self):
        """Test when user is not a manager"""
        from src.api.auth_api import allow_shop_manager
        from src.model.staff_model import StaffModel
    
        mock_staff = MagicMock(spec=StaffModel)
        mock_staff.role = "staff"
    
        with patch('src.api.auth_api.get_current_staff') as mock_get_staff:
            mock_get_staff.return_value = mock_staff

            with pytest.raises(HTTPException) as exc_info:
                await allow_shop_manager(mock_staff)
            
            assert exc_info.value.status_code == 403


class TestWxLogin:
    """Test wx_login endpoint"""
    
    async def test_wx_login_success_new_user(self):
        """Test successful login for new user"""
        from src.api.auth_api import wx_login, WxLoginPayload
        from src.model.user_model import UserModel
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class, \
             patch('src.api.auth_api.get_db') as mock_get_db:
        
            # Setup mock HTTP client - need to make it async
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "openid": "test_openid",
                "unionid": "test_unionid"
            }
            
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            
            # Make the client work with async context manager
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
        
            # Setup mock database
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            # Mock the UserModel creation and commit
            mock_user = MagicMock(spec=UserModel)
            mock_user.id = 123
            mock_user.openid = "test_openid"
            
            def add_side_effect(obj):
                if isinstance(obj, UserModel):
                    return
                # For StaffModel
                obj.id = 456
                obj.user_id = 123
                obj.shop_id = 1
                obj.name = "手机店员"
                obj.role = "staff"
                obj.status = 1
            
            mock_db.add.side_effect = add_side_effect
            mock_db.flush.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            mock_get_db.return_value = mock_db
        
            payload = WxLoginPayload(code="test_code")
            result = await wx_login(payload, mock_db)
            
            # Check that the response has the expected structure
            assert hasattr(result, 'token')
            assert result.token is not None
    
    async def test_wx_login_empty_code(self):
        """Test with empty code"""
        from src.api.auth_api import wx_login, WxLoginPayload
        from src.common.exceptions import BusinessException
        
        payload = WxLoginPayload(code="")
        with pytest.raises(BusinessException) as exc_info:
            await wx_login(payload, MagicMock())
        
        assert exc_info.value.status_code == 400
    
    async def test_wx_login_weixin_error(self):
        """Test when Weixin API returns error"""
        from src.api.auth_api import wx_login, WxLoginPayload
        from src.common.exceptions import BusinessException
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class:
            # Setup mock HTTP client that returns error - need to make it async
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "errcode": 40029,
                "errmsg": "code invalid"
            }
            
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            
            # Make the client work with async context manager
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            payload = WxLoginPayload(code="invalid_code")
            with pytest.raises(BusinessException) as exc_info:
                await wx_login(payload, MagicMock())
    
            assert exc_info.value.status_code == 400
    
    async def test_wx_login_missing_openid(self):
        """Test when Weixin API doesn't return openid"""
        from src.api.auth_api import wx_login, WxLoginPayload
        from src.common.exceptions import BusinessException
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class:
            # Setup mock HTTP client that returns response without openid - need to make it async
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "unionid": "test_unionid"
            }
            
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            
            # Make the client work with async context manager
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            payload = WxLoginPayload(code="test_code")
            with pytest.raises(BusinessException) as exc_info:
                await wx_login(payload, MagicMock())
    
            assert exc_info.value.status_code == 400
    
    async def test_wx_login_existing_user(self):
        """Test successful login for existing user"""
        from src.api.auth_api import wx_login, WxLoginPayload
        from src.model.user_model import UserModel
        
        # Create a real UserModel instance instead of MagicMock
        # Add all required fields for LoginResponse validation
        mock_user = UserModel(
            id=456,
            openid="existing_openid",
            default_shop_id=None,
            default_staff_id=None
        )
    
        # Mock staff profile with proper attributes for UserResponse validation
        from src.model.staff_model import StaffModel
        
        # Create a real StaffModel instance instead of MagicMock
        mock_staff = StaffModel(
            id=789,
            shop_id=123,
            user_id=456,  # Must match mock_user.id
            phone="13800000001",
            name="Test Staff",  # Use 'name' not 'nickname'
            role="staff",
            status=1,  # Active
            avatar="https://example.com/avatar.jpg"
        )
        
        with patch('src.api.auth_api.httpx.AsyncClient') as mock_client_class, \
             patch('src.api.auth_api.get_db') as mock_get_db:
            
            # Setup mock HTTP client - need to make it async
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "openid": "existing_openid",
                "unionid": "test_unionid"
            }
            
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            
            # Make the client work with async context manager
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            # Setup mock database with existing user and staff profile
            mock_db = MagicMock()
    
            # Mock the first() method to return actual instances
            # Need to track which model is being queried
            query_count = [0]
            def first_side_effect(*args, **kwargs):
                query_count[0] += 1
                print(f"\nDEBUG: Query #{query_count[0]}, args={args}, kwargs={kwargs}")
                
                # Check if this is a UserModel query or StaffModel query
                model_cls = None
                for arg in args:
                    if hasattr(arg, '__name__') and 'UserModel' in arg.__name__:
                        print("DEBUG: This is a UserModel query")
                        return mock_user
                    elif hasattr(arg, '__name__') and 'StaffModel' in arg.__name__:
                        print(f"DEBUG: This is a StaffModel query, returning staff with user_id={mock_staff.user_id}")
                        return mock_staff
                
                if query_count[0] == 1:  # UserModel query (line 230)
                    print("DEBUG: Returning mock_user")
                    return mock_user
                elif query_count[0] == 2:  # StaffModel query for existing user (line 262-265)
                    print(f"DEBUG: Returning mock_staff, type={type(mock_staff)}, name={mock_staff.name}")
                    return mock_staff
                else:
                    print("DEBUG: Returning None")
                    return None
            
    
            # Setup the mock to return actual instances
            # The query.filter().order_by().first() chain needs to be mocked properly
            def query_side_effect(model_cls):
                """Mock db.query() to track which model is being queried"""
                print(f"\nDEBUG: db.query() called with {model_cls}")
                
                # Create a mock filter chain that returns itself
                mock_filter = MagicMock()
                mock_filter.filter.return_value = mock_filter  # Allow chaining
                mock_filter.order_by.return_value = mock_filter  # Allow order_by chaining
                
                def first_side_effect_for_model(*args, **kwargs):
                    """Handle the .first() call"""
                    print(f"DEBUG: .first() called on query for {model_cls}")
                    
                    # Check if this is UserModel or StaffModel
                    if 'UserModel' in str(model_cls):
                        print("DEBUG: Returning mock_user from first()")
                        return mock_user
                    elif 'StaffModel' in str(model_cls):
                        print(f"DEBUG: Returning mock_staff from first(), staff.user_id={mock_staff.user_id}")
                        return mock_staff
                    return None
                
                mock_filter.first.side_effect = first_side_effect_for_model
                return mock_filter
            
            # Mock db.query to accept the model class and return filter chain
            mock_db.query.side_effect = query_side_effect
            mock_get_db.return_value = mock_db
            
            # Add debug output to trace execution flow
            import sys
            from io import StringIO
            
            # Capture print statements
            old_stdout = sys.stdout
            new_stdout = StringIO()
            sys.stdout = new_stdout
            
            payload = WxLoginPayload(code="test_code")
            
            # Add debug to see what staff is returned
            original_wx_login = wx_login.__wrapped__ if hasattr(wx_login, '__wrapped__') else wx_login
            
            result = await wx_login(payload, mock_db)
            
            # Restore stdout and get output
            sys.stdout = old_stdout
            debug_output = new_stdout.getvalue()
            print("\n=== DEBUG OUTPUT ===")
            print(debug_output)
            print("=== END DEBUG ===\n")
            
            # Check that the response has the expected structure
            assert hasattr(result, 'token')
            assert isinstance(result.token, str)
            assert len(result.token) > 0


class TestGetMyInfo:
    """Test get_my_info endpoint"""
    
    async def test_get_my_info_success(self):
        """Test successful info retrieval"""
        from src.api.auth_api import get_my_info
        from src.model.user_model import UserModel
        from src.model.staff_model import StaffModel
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.openid = "test_openid"
        
        # Create a real StaffModel instance with proper attributes for validation
        from datetime import datetime
        mock_staff = StaffModel(
            id=456,
            shop_id=789,
            user_id=123,
            phone="13800000000",
            name="Test User",
            role="staff",
            status=1,
            avatar="test_avatar.jpg",
            created_at=datetime.now()
        )
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            # Setup mocks
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            result = await get_my_info(x_shop_id=789, db=mock_db, current_user=mock_user)
        
            # Result is a UserResponse model object
            assert hasattr(result, 'nickname') and result.nickname == "Test User"
            assert hasattr(result, 'avatar_url') and result.avatar_url == "test_avatar.jpg"
    
    async def test_get_my_info_not_found(self):
        """Test when staff profile not found"""
        from src.api.auth_api import get_my_info
        from src.common.exceptions import BusinessException
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(BusinessException):
                await get_my_info(x_shop_id=789, db=mock_db, current_user=mock_user)
    
    async def test_get_my_info_inactive_staff(self):
        """Test when staff is inactive - should raise BusinessException"""
        from src.api.auth_api import get_my_info
        from src.model.staff_model import StaffModel
        from src.common.exceptions import BusinessException
        
        # Create a real UserModel instance with proper attributes for validation
        from src.model.user_model import UserModel
        from datetime import datetime
        
        mock_user = UserModel(
            id=123,
            openid="test_openid",
            default_shop_id=None,
            default_staff_id=None
        )
        
        # Create a real StaffModel instance with proper attributes for validation
        from datetime import datetime
        mock_staff = StaffModel(
            id=456,
            shop_id=789,
            user_id=123,
            phone="13800000000",
            name="Test User",
            role="staff",
            status=0,  # Inactive
            avatar="test_avatar.jpg",
            created_at=datetime.now()
        )
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            # First query (status == 1) returns None - no active staff found
            mock_db.query.return_value.filter.return_value.first.side_effect = [None, mock_staff]
            mock_get_db.return_value = mock_db
            
            # Should raise BusinessException for inactive staff
            with pytest.raises(BusinessException):
                await get_my_info(x_shop_id=789, db=mock_db, current_user=mock_user)


class TestUpdateMyInfo:
    """Test update_my_info endpoint"""
    
    async def test_update_my_info_success(self):
        """Test successful info update"""
        from src.api.auth_api import update_my_info
        from src.model.user_model import UserModel
        from src.model.staff_model import StaffModel
        from src.model.schema import UserUpdateSchema
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.nickname = "Old Name"
        mock_user.avatar_url = "old_avatar.jpg"
        mock_user.role = "staff"
        
        # Create a real StaffModel instance with proper attributes for validation
        from datetime import datetime
        mock_staff = StaffModel(
            id=456,
            shop_id=789,
            user_id=123,
            phone="13800000000",
            name="Old Name",
            role="staff",
            status=1,
            avatar="old_avatar.jpg",
            created_at=datetime.now()
        )
        
        # Create a proper Pydantic model instance
        # Note: avatar field maps to avatar_url in the schema
        update_data = UserUpdateSchema(nickname="New Name", avatar_url="new_avatar.jpg")
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            # Setup mocks
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_staff
            mock_get_db.return_value = mock_db
            
            result = update_my_info(user_in=update_data, x_shop_id=789, current_user=mock_user, db=mock_db)
        
            # Result is a UserResponse model object
            assert hasattr(result, 'nickname') and result.nickname == "New Name"
            assert hasattr(result, 'avatar_url') and result.avatar_url == "new_avatar.jpg"
    
    async def test_update_my_info_no_fields(self):
        """Test with no update fields provided"""
        from src.api.auth_api import update_my_info
        from src.common.exceptions import BusinessException
        from src.model.schema import UserUpdateSchema
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        # Create an empty Pydantic model instance
        update_data = UserUpdateSchema()
        
        with pytest.raises(BusinessException) as exc_info:
            await update_my_info(user_in=update_data, x_shop_id=789, current_user=mock_user, db=MagicMock())
        
        # Check for Chinese error message
        assert "字段" in str(exc_info.value)
    
    async def test_update_my_info_invalid_default_shop(self):
        """Test with invalid default shop"""
        from src.api.auth_api import update_my_info
        from src.common.exceptions import BusinessException
        from src.model.schema import UserUpdateSchema
        
        mock_user = MagicMock()
        mock_user.id = 123
        
        # Create a proper Pydantic model instance
        update_data = UserUpdateSchema(default_shop_id=999)
        
        with patch('src.api.auth_api.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            with pytest.raises(BusinessException) as exc_info:
                await update_my_info(user_in=update_data, x_shop_id=789, current_user=mock_user, db=mock_db)
            
            # Check for Chinese error message about shop/identity
            assert "店铺" in str(exc_info.value) or "身份" in str(exc_info.value)


class TestPermissionChecker:
    """Test PermissionChecker class"""
    
    async def test_permission_checker_allowed(self):
        """Test when user has required role"""
        from src.api.auth_api import PermissionChecker
        from src.model.user_model import UserModel
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.role = "manager"
        
        checker = PermissionChecker(["manager"])
        result = checker(current_user=mock_user)
        
        assert result is not None
    
    async def test_permission_checker_forbidden(self):
        """Test when user doesn't have required role"""
        from src.api.auth_api import PermissionChecker
        from src.model.user_model import UserModel
        from fastapi import HTTPException, status
        
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 123
        mock_user.role = "staff"
        
        checker = PermissionChecker(["admin"])
        with pytest.raises(HTTPException) as exc_info:
            result = checker(current_user=mock_user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "暂无访问权限"
