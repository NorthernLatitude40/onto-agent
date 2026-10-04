"""
Authentication API Endpoints

This module provides authentication-related endpoints including:
- User identity management (/auth/me)
- WeChat login (/auth/wx-login)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from src.model.user_model import UserModel as User
from src.model.response_models import ApiResponse, UserResponse
from src.common.database import get_db
from src.common.exceptions import NotFoundError, UnauthorizedError
from src.api.auth_api import get_current_user as get_current_user_from_token

router = APIRouter(tags=["auth"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="獲取當前用戶信息",
    description="返回當前登錄用戶的基本信息"
)
async def get_current_user(
    current_user: User = Depends(get_current_user_from_token)
):
    """
    獲取當前用戶信息
    
    Returns:
        UserResponse: 當前用戶的基本信息
    
    Raises:
        UnauthorizedError: 如果用戶未登錄或會話無效
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role
    )


@router.put(
    "/me",
    response_model=ApiResponse,
    summary="更新當前用戶信息",
    description="允許用戶更新自己的基本信息"
)
async def update_current_user(
    current_user: User = Depends(get_current_user_from_token)
):
    """
    更新當前用戶信息
    
    Returns:
        ApiResponse: 操作結果
    
    Raises:
        UnauthorizedError: 如果用戶未登錄或會話無效
    """
    # TODO: Implement actual update logic with current_user
    return ApiResponse(
        code=200,
        message="User information updated successfully"
    )


@router.post(
    "/wx-login",
    response_model=ApiResponse,
    summary="WeChat登錄",
    description="使用WeChat授權碼進行登錄"
)
async def wx_login(
    db: Session = Depends(get_db)
):
    """
    WeChat登錄
    
    Returns:
        ApiResponse: 登錄結果和會話信息
    
    Raises:
        BadRequestError: 如果授權碼無效或已過期
    """
    # TODO: Implement actual WeChat login logic with db session
    return ApiResponse(
        code=200,
        message="WeChat login successful",
        data={
            "token": "mock_jwt_token_here",
            "expires_in": 7200,
            "user_id": 1
        }
    )
