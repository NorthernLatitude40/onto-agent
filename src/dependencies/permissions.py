# src/deps/permissions.py
from typing import List, Union
from enum import Enum
from fastapi import Depends, HTTPException, status
from src.model.user_model import User
from src.api.auth_api import get_current_user

# 1. 使用 Enum 定义角色，彻底消除硬编码字符串
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"

# 2. 通用权限校验器类
class RoleChecker:
    def __init__(self, allowed_roles: List[Union[UserRole, str]]):
        # 兼容 Enum 和纯字符串
        self.allowed_roles = [r.value if isinstance(r, Enum) else r for r in allowed_roles]

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作"
            )
        return current_user

# 3. 预定义常用权限快捷依赖项 (极度优雅，直接在路由点用)
allow_admin = RoleChecker([UserRole.ADMIN])
allow_admin_or_manager = RoleChecker([UserRole.ADMIN, UserRole.MANAGER])
allow_all_staff = RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.STAFF])