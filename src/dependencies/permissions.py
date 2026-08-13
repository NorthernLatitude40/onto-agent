# src/deps/permissions.py
from typing import List, Union, Optional
from enum import Enum
from fastapi import Depends, status, Header, Query, Path
from sqlalchemy.orm import Session

# 💡 请根据你的项目目录确保导入路径正确
from src.model.user_model import User
from src.model.staff_model import StaffModel
from src.api.auth_api import get_current_user
from src.common.database import get_db                  # 补全 get_db 导入
from src.common.exceptions import BusinessException, PermissionDeniedException
from src.common.dict import SystemRole, ShopRole


# ==============================================================================
# 2. 系统权限校验器
# ==============================================================================
class SystemRoleChecker:
    def __init__(self, allowed_roles: List[Union[SystemRole, str]]):
        # 兼容 Enum 和纯字符串
        self.allowed_roles = [r.value if isinstance(r, Enum) else r for r in allowed_roles]

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        # 假设 User 模型中的系统角色字段为 system_role（若为 role 请调整为 current_user.role）
        user_role = getattr(current_user, "system_role", getattr(current_user, "role", None))
        
        if user_role not in self.allowed_roles:
            raise PermissionDeniedException()
        return current_user


# 预定义系统级权限快捷依赖项
allow_admin = SystemRoleChecker([SystemRole.ADMIN])


# ==============================================================================
# 3. 店铺/租户权限校验器
# ==============================================================================

# 定义默认的开发/测试店铺 ID
DEFAULT_TEST_SHOP_ID = 1

class ShopRoleChecker:
    def __init__(self, allowed_shop_roles: List[Union[ShopRole, str]]):
        self.allowed_shop_roles = [r.value if isinstance(r, Enum) else r for r in allowed_shop_roles]

    def __call__(
        self,
        # 1. 设置 Header 可选，默认值为 None
        shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
        sys_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> Optional[StaffModel]:
        

        # 1. 如果是平台超管，直接放行
        user_system_role = getattr(sys_user, "system_role", getattr(sys_user, "role", None))
        if user_system_role == SystemRole.ADMIN.value or user_system_role == SystemRole.ADMIN:
            staff_relation = StaffModel(
                    shop_id=DEFAULT_TEST_SHOP_ID,
                    id=0,
                    user_id=sys_user.id,
                    name="admin",
                    role=ShopRole.OWNER,
                    status=1
                )
            return staff_relation

        # 🚀 2. 核心调整：如果前端没传 Header，固定使用测试店铺 ID (比如 1)
        target_shop_id = shop_id if shop_id is not None else DEFAULT_TEST_SHOP_ID

        # 3. 查询用户在该店铺下的具体角色
        staff_relation = db.query(StaffModel).filter(
            StaffModel.shop_id == target_shop_id,
            StaffModel.user_id == sys_user.id
        ).first()

        # 4. 未绑定店铺或已禁用
        if not staff_relation:
            raise BusinessException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="NOT_SHOP_STAFF",
                message=f"当前用户未绑定店铺 ID 为 {target_shop_id} 的员工权限"
            )

        # 5. 校验店铺内角色是否合规
        if staff_relation.role not in self.allowed_shop_roles:
            raise PermissionDeniedException()

        return staff_relation


# 预定义店铺级权限快捷依赖项：
# 店长/老板及以上
allow_shop_manager = ShopRoleChecker([ShopRole.OWNER, ShopRole.MANAGER])

# 普通店员及以上（老板、店长、店员均可）
allow_shop_staff = ShopRoleChecker([ShopRole.OWNER, ShopRole.MANAGER, ShopRole.STAFF])