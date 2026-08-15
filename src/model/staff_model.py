from datetime import datetime
from sqlalchemy import Column, Integer, String, SmallInteger, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from src.common.database import Base

class StaffModel(Base):
    __tablename__ = "staff"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 1. 关联门店：直接外键关联 Shop（1 个 Staff 属于 1 个门店）
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 2. 关联微信用户：允许为 None！预录入时为空，扫码后绑定 user_id
    user_id = Column(BigInteger, ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 3. 基础与岗位信息
    phone = Column(String(20), nullable=False, index=True) # 预留手机号（用于匹配绑定）
    name = Column(String(50), nullable=False)        # 真实姓名
    role = Column(String(20), nullable=False, default="staff") # 'manager', 'staff'
    status = Column(SmallInteger, nullable=False, default=0)    # 0: 待绑定/未激活, 1: 正常在职, 2: 禁用/离职
    avatar = Column(String(255), default="")
    
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    # ORM 关联映射
    shop = relationship("ShopModel", back_populates="staffs")
    user = relationship("UserModel", back_populates="staff_employments")