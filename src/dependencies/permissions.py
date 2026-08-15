# src/deps/permissions.py
from typing import List, Union, Optional
from enum import Enum
from fastapi import Depends, status, Header
from sqlalchemy.orm import Session

from src.model.user_model import UserModel
from src.model.staff_model import StaffModel
from src.api.auth_api import get_current_user
from src.common.database import get_db
from src.common.exceptions import BusinessException, PermissionDeniedException
from src.common.dict import ShopRole
from src.common.i18n import ErrorCode


# 定义默认的开发/测试店铺 ID
DEFAULT_TEST_SHOP_ID = 1


# ==============================================================================
# 店铺/租户权限校验器 (单表架构版)
# ==============================================================================
class ShopRoleChecker:
    def __init__(self, allowed_shop_roles: List[Union[ShopRole, str]]):
        # 兼容 Enum 和纯字符串
        self.allowed_shop_roles = [r.value if isinstance(r, Enum) else r for r in allowed_shop_roles]

    def __call__(
        self,
        shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
        staff_id: Optional[int] = Header(None, alias="X-Staff-Id", description="当前选择的StaffID"),
        current_user: UserModel = Depends(get_current_user), # 🌟 统一依赖 UserModel
        db: Session = Depends(get_db)
    ) -> StaffModel:
        # 1. 确定目标店铺 ID (若无 Header 传参，回退默认测试店铺)
        target_shop_id = shop_id if shop_id is not None else DEFAULT_TEST_SHOP_ID

        # ---------------------------------------------------------
        # 特权 1：如果是平台超级管理员 (System Admin)，直接授权放行
        # ---------------------------------------------------------
        if getattr(current_user, "role", None) == "admin":
            # 如果超管在该店铺有真实档案则拿真实档案，没有则构建临时全权档案
            admin_staff = db.query(StaffModel).filter(
                StaffModel.user_id == current_user.id,
                StaffModel.shop_id == target_shop_id
            ).first()

            if not admin_staff:
                admin_staff = StaffModel(
                    id=current_user.id,
                    user_id=current_user.id,
                    shop_id=target_shop_id,
                    name=getattr(current_user, "nickname", "超级管理员"),
                    role=ShopRole.ADMIN.value,
                    status=1
                )
            return admin_staff

        # ---------------------------------------------------------
        # 2. 从 StaffModel 单表中精准定位员工档案 (替代原来的 ShopStaffModel)
        # ---------------------------------------------------------
        staff = db.query(StaffModel).filter(
            StaffModel.user_id == current_user.id,
            StaffModel.shop_id == target_shop_id,
            StaffModel.id == staff_id
        ).first()

        # 3. 未绑定店铺或档案不存在
        if not staff:
            raise BusinessException(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.NOT_SHOP_STAFF,
                detail=f"当前用户未绑定店铺 ID 为 {target_shop_id} 的员工权限"
            )

        # 4. 账号被禁用/已离职 ( status == 2 或 != 1 )
        if staff.status != 1:
            raise BusinessException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="STAFF_DISABLED",
                detail="您在该店铺的员工账号已被禁用或尚未激活"
            )

        # ---------------------------------------------------------
        # 特权 2：店铺 Owner (Boss) 拥有当前店铺最高权限，直接放行
        # ---------------------------------------------------------
        if staff.role == ShopRole.OWNER.value:
            return staff

        # 5. 校验当前员工角色是否符合接口所需的权限列表
        if staff.role not in self.allowed_shop_roles:
            raise PermissionDeniedException()

        return staff


# ==============================================================================
# 快捷权限依赖项导出
# ==============================================================================

# 店长/老板/管理员 及以上
allow_shop_manager = ShopRoleChecker([ShopRole.OWNER, ShopRole.ADMIN, ShopRole.MANAGER])

# 普通店员及以上（Boss、管理员、店长、店员均可）
allow_shop_staff = ShopRoleChecker([ShopRole.OWNER, ShopRole.ADMIN, ShopRole.MANAGER, ShopRole.STAFF])