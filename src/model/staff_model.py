from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, SmallInteger, func, UniqueConstraint
from sqlalchemy.orm import relationship
from src.common.database import Base

class StaffModel(Base):
    """
    店铺与员工的绑定关系表（一对多或多对多）
    """
    __tablename__ = "staff"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False, index=True)
    
    # 🌟 关键：未被接纳认领前，user_id 为 None！绝对不存假 OpenID！
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True)
    
    name = Column(String(64), nullable=False, comment="管理员填写的员工姓名/备注")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 對應 UserModel 裡的 staff_profiles 屬性
    user = relationship("User", back_populates="staff_profiles")

    shop_employments = relationship("ShopStaffModel", back_populates="staff")
