# src/core/shop_agent/models.py
import enum
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime

class UserRole(str, enum.Enum):
    ADMIN = "admin"      # 超级管理员（全部权限）
    MANAGER = "manager"  # 店长（查看财务报表、修改设备、管理店员）
    STAFF = "staff"      # 普通店员（只能录入入库/出售，无权看核心财务数据）
    
class User(Base):
    __tablename__ = "sys_user"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False, index=True)
    unionid = Column(String(64), nullable=True)
    nickname = Column(String(64), default="微信用户")
    avatar_url = Column(String(255), default="")
    phone = Column(String(20), nullable=True)
    role = Column(String(20), default=UserRole.STAFF.value, nullable=False) # 默认店员
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())