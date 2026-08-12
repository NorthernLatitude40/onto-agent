# src/core/shop_agent/models.py
import enum
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index, Boolean
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime
from src.common.dict import SystemRole


    
class User(Base):
    __tablename__ = "sys_user"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False, index=True)
    unionid = Column(String(64), nullable=True)
    nickname = Column(String(64), default="微信用户")
    avatar_url = Column(String(255), default="")
    phone = Column(String(20), nullable=True)
    role = Column(String(20), default=SystemRole.MERCHANT.value, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, comment="是否激活")

    # 1. 必须添加 ForeignKey，指向 shops 表的 id 字段！
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=True, comment="所属店铺ID")

    # 2. (可选) 配置反向关联
    shop = relationship("ShopModel", back_populates="users")