"""
User Registration API Endpoints

This module provides user registration functionality including:
- User registration (/api/v1/auth/register)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional
import re

from src.model.user_model import UserModel
from src.model.response_models import ApiResponse
from src.common.database import get_db
from src.common.exceptions import BadRequestError

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, description="Username must be at least 3 characters long")
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")

router = APIRouter(prefix="", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse,
    summary="用户注册",
    description="创建新用户账号"
)
def register_user(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    用户注册
    
    Parameters:
        username: 用户名
        email: 电子邮件地址
        password: 密码（最少6个字符）
    
    Returns:
        ApiResponse: 注册结果
    
    Raises:
        BadRequestError: 如果参数无效或用户已存在
    """
    # 验证输入参数
    username = request.username
    email = request.email
    password = request.password
    
    # 检查用户是否已存在
    existing_user_by_username = db.query(UserModel).filter(UserModel.openid == username).first()
    existing_user_by_email = db.query(UserModel).filter(UserModel.email == email).first()
    
    if existing_user_by_username:
        raise BadRequestError("Username already exists")
    
    if existing_user_by_email:
        raise BadRequestError("Email already registered")
    
    # 创建新用户（使用openid字段作为username，email字段保存邮箱）
    new_user = UserModel(
        openid=username,
        email=email
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return ApiResponse(
        code=201,
        message="User registered successfully",
        data={
            "user_id": new_user.id,
            "username": username,
            "email": email
        }
    )
