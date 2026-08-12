from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, SmallInteger, func, UniqueConstraint
from sqlalchemy.orm import relationship
from src.common.database import Base

class StaffModel(Base):
    """
    店铺与员工的绑定关系表（一对多或多对多）
    """
    __tablename__ = "shop_staff"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False, index=True)
    
    # 🌟 关键：未被接纳认领前，user_id 为 None！绝对不存假 OpenID！
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True)
    
    name = Column(String(64), nullable=False, comment="管理员填写的员工姓名/备注")
    role = Column(String(20), default="staff", nullable=False, comment="角色: owner/manager/staff")
    
    # 状态：0: 待认领(待接受邀请), 1: 正常在职, 2: 已离职/禁用
    status = Column(SmallInteger, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 1. 建立与 User 的 ORM 关系（确保 User 对应的 __tablename__ 为 sys_user）
    user = relationship("User", backref="staff_profiles")

    # 2. 反向关联到店铺 (一个员工属于一个店铺)
    shop = relationship("ShopModel", back_populates="staffs", foreign_keys=[shop_id])

    __table_args__ = (
        UniqueConstraint('shop_id', 'user_id', name='uix_shop_user'), 
    )