"""
Unit tests for clark_api.py endpoints
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from src.api.v1.endpoints.clark_api import (
    create_staff,
    update_staff,
    get_staff_list,
    generate_invite,
    accept_invite,
)
from src.model.staff_model import StaffModel
from src.model.user_model import UserModel
from src.model.clark_schema import StaffUpdateSchema
from src.common.exceptions import BusinessException


@pytest.fixture
def anyio_backend():
    # 只跑 asyncio，不跑 trio
    return "asyncio"


def make_manager():
    user = MagicMock(spec=StaffModel)
    user.id = 1
    user.role = "manager"
    user.shop_id = 1
    return user


class TestCreateStaff:
    def test_create_staff_success(self):
        db = MagicMock(spec=Session)
        db.query().filter().first.return_value = None  # 無重複
        # 模擬資料庫在 refresh 時回填主鍵
        db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)

        req = SimpleNamespace(nickname="张三", phone=None, role="staff")

        result = create_staff(
            req=req, db=db, current_user=make_manager(), x_shop_id="1"
        )

        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert result.id == 1
        assert result.nickname == "张三"
        assert result.role == "staff"
        assert result.status == 0
        assert result.is_active is False

    def test_create_staff_duplicate_name(self):
        db = MagicMock(spec=Session)
        existing = MagicMock(spec=StaffModel)
        existing.id = 2
        existing.name = "张三"
        existing.status = 0
        db.query().filter().first.return_value = existing

        req = SimpleNamespace(nickname="张三", phone=None, role="staff")

        with pytest.raises(BusinessException) as exc_info:
            create_staff(req=req, db=db, current_user=make_manager(), x_shop_id="1")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "已存在名为 '张三' 的待接受邀请员工" in exc_info.value.detail
        db.add.assert_not_called()

    def test_create_staff_invalid_shop_id(self):
        req = SimpleNamespace(nickname="张三", phone=None, role="staff")

        with pytest.raises(BusinessException) as exc_info:
            create_staff(
                req=req,
                db=MagicMock(spec=Session),
                current_user=make_manager(),
                x_shop_id="invalid",
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "非法的 X-Shop-Id" in exc_info.value.detail


class TestUpdateStaff:
    def test_update_staff_success(self):
        db = MagicMock(spec=Session)
        target = MagicMock(spec=StaffModel)
        target.id = 2
        target.name = "张三"
        target.role = "staff"
        target.status = 0
        db.query().filter().first.return_value = target

        payload = StaffUpdateSchema(id=2, name="李四", role="manager", status=None)

        result = update_staff(
            payload=payload,
            staff_id=2,
            shop_id=1,
            db=db,
            current_user=make_manager(),
        )

        db.commit.assert_called_once()
        assert result.id == 2
        assert result.nickname == "李四"
        assert result.role == "manager"

    def test_update_staff_not_found(self):
        db = MagicMock(spec=Session)
        db.query().filter().first.return_value = None

        payload = StaffUpdateSchema(id=2, name="李四", role="manager", status=None)

        with pytest.raises(BusinessException) as exc_info:
            update_staff(
                payload=payload,
                staff_id=2,
                shop_id=1,
                db=db,
                current_user=make_manager(),
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "找不到该员工档案" in exc_info.value.detail

    def test_update_staff_manager_cannot_modify_owner(self):
        db = MagicMock(spec=Session)
        target = MagicMock(spec=StaffModel)
        target.id = 2
        target.name = "店主"
        target.role = "owner"
        target.status = 1
        db.query().filter().first.return_value = target

        payload = StaffUpdateSchema(id=2, name="店主", role="staff", status=None)

        with pytest.raises(BusinessException) as exc_info:
            update_staff(
                payload=payload,
                staff_id=2,
                shop_id=1,
                db=db,
                current_user=make_manager(),
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "店长(manager)无法变更店主(owner)的角色" in exc_info.value.detail
        db.commit.assert_not_called()


class TestGetStaffList:
    @patch("src.api.v1.endpoints.clark_api.create_access_token", return_value="tok")
    def test_get_staff_list_success(self, _mock_token):
        db = MagicMock(spec=Session)

        current_user = MagicMock(spec=UserModel)
        current_user.id = 1
        current_user.role = "owner"

        staff1 = MagicMock(spec=StaffModel)
        staff1.id = 1
        staff1.name = "张三"
        staff1.role = "manager"
        staff1.status = 1
        staff1.shop_id = 1

        staff2 = MagicMock(spec=StaffModel)
        staff2.id = 2
        staff2.name = "李四"
        staff2.role = "staff"
        staff2.status = 0
        staff2.shop_id = 1

        db.query().filter().first.return_value = staff1
        db.query().filter().all.return_value = [staff1, staff2]

        result = get_staff_list(x_shop_id=1, db=db, current_user=current_user)

        assert result["code"] == 200
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "张三"
        assert result["data"][0]["invite_token"] is None
        assert result["data"][1]["name"] == "李四"
        assert result["data"][1]["invite_token"] == "tok"  # 待激活员工才有 token

    def test_get_staff_list_no_permission(self):
        db = MagicMock(spec=Session)

        current_user = MagicMock(spec=UserModel)
        current_user.id = 1
        current_user.role = "staff"

        db.query().filter().first.return_value = None

        with pytest.raises(BusinessException) as exc_info:
            get_staff_list(x_shop_id=1, db=db, current_user=current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "无权管理该店铺的员工档案" in exc_info.value.detail


class TestGenerateInvite:
    def test_generate_invite_success(self):
        db = MagicMock(spec=Session)
        staff = MagicMock(spec=StaffModel)
        staff.id = 2
        staff.name = "张三"
        staff.shop_id = 1
        db.query().filter().first.return_value = staff

        req = SimpleNamespace(staff_id=2, shop_id=1)

        result = generate_invite(req=req, db=db, current_admin=MagicMock(spec=UserModel))

        assert result["code"] == 200
        assert result["data"]["staff_id"] == 2
        assert result["data"]["staff_name"] == "张三"
        assert "INVITE_2_1_" in result["data"]["invite_token"]

    def test_generate_invite_not_found(self):
        db = MagicMock(spec=Session)
        db.query().filter().first.return_value = None

        req = SimpleNamespace(staff_id=2, shop_id=1)

        with pytest.raises(BusinessException) as exc_info:
            generate_invite(req=req, db=db, current_admin=MagicMock(spec=UserModel))

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "未找到该员工档案" in exc_info.value.detail


@pytest.mark.anyio
class TestAcceptInvite:
    @staticmethod
    def _make_user():
        user = MagicMock(spec=UserModel)
        user.id = 1
        user.openid = "test_openid"
        return user

    @staticmethod
    def _make_staff():
        staff = MagicMock(spec=StaffModel)
        staff.id = 2
        staff.name = "张三"
        staff.shop_id = 1
        staff.role = "staff"
        staff.status = 0
        staff.user_id = None
        return staff

    @patch("src.api.v1.endpoints.clark_api.create_access_token")
    async def test_accept_invite_success(self, mock_create_access_token):
        db = MagicMock(spec=Session)
        user = self._make_user()
        staff = self._make_staff()
        # 查询顺序：UserModel -> StaffModel(指定ID) -> 其他激活档案(A2 查重)
        db.query().filter().first.side_effect = [user, staff, None]

        req = SimpleNamespace(code="TEST_CODE", invite_token="test.token.here", shop_id=None)

        with patch("src.api.v1.endpoints.clark_api.jwt.decode") as mock_jwt_decode, patch(
            "src.api.v1.endpoints.clark_api.get_wx_openid_by_code",
            new_callable=AsyncMock,
        ) as mock_wx:
            mock_jwt_decode.return_value = {"shop_id": 1, "staff_id": 2}
            mock_wx.return_value = {"openid": "test_openid"}
            mock_create_access_token.return_value = "new.access.token"

            result = await accept_invite(req=req, db=db)

        assert result["token"] == "new.access.token"
        assert result["shop_id"] == 1
        assert result["staff_id"] == 2
        assert staff.status == 1
        assert staff.user_id == 1

    async def test_accept_invite_invalid_token(self):
        db = MagicMock(spec=Session)
        req = SimpleNamespace(code="TEST_CODE", invite_token="invalid.token", shop_id=None)

        with pytest.raises(BusinessException) as exc_info:
            await accept_invite(req=req, db=db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "邀请凭证已失效或不合法" in exc_info.value.detail

    async def test_accept_invite_user_already_has_other_active_profile(self):
        """覆蓋 A2 查重分支（原本會因為 BusinessException 簽名錯誤而 TypeError）"""
        db = MagicMock(spec=Session)
        user = self._make_user()
        staff = self._make_staff()
        other_active = MagicMock(spec=StaffModel)
        db.query().filter().first.side_effect = [user, staff, other_active]

        req = SimpleNamespace(code="TEST_CODE", invite_token="test.token.here", shop_id=None)

        with patch("src.api.v1.endpoints.clark_api.jwt.decode") as mock_jwt_decode, patch(
            "src.api.v1.endpoints.clark_api.get_wx_openid_by_code",
            new_callable=AsyncMock,
        ) as mock_wx:
            mock_jwt_decode.return_value = {"shop_id": 1, "staff_id": 2}
            mock_wx.return_value = {"openid": "test_openid"}

            with pytest.raises(BusinessException) as exc_info:
                await accept_invite(req=req, db=db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.code == "ALREADY_MEMBER"