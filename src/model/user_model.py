# src/core/shop_agent/models.py
import enum
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index, Boolean
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime


    
class UserModel(Base):
    __tablename__ = "sys_user"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False)
    
    # 1个微信用户可以拥有多个 staff 履职记录（支持一人兼任多店）
    staff_employments = relationship("StaffModel", back_populates="user")