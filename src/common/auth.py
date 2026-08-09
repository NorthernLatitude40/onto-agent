# src/common/deps.py (或 auth.py)
from typing import List
from fastapi import Depends, HTTPException, status
from src.model.user_model import User, UserRole
from src.api.auth_api import get_current_user # 导入之前写的获取当前用户函数

def require_roles(allowed_roles: List[UserRole]):
    """
    角色权限拦截器闭包
    用法: Depends(require_roles([UserRole.ADMIN, UserRole.MANAGER]))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in [role.value for role in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：当前角色 [{current_user.role}] 无法访问此功能"
            )
        return current_user

    return role_checker