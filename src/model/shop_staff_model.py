from datetime import datetime
from sqlalchemy import Column, Integer, String, SmallInteger, DateTime, ForeignKey, UniqueConstraint, BigInteger
from sqlalchemy.orm import relationship
from src.common.database import Base # 根據你的項目引入 Base

class ShopStaffModel(Base):
    __tablename__ = "shop_staff"

    id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(BigInteger, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="staff")  # 'manager', 'staff'
    status = Column(SmallInteger, nullable=False, default=1)    # 1: active, 0: disabled
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 聯合唯一限制
    __table_args__ = (
        UniqueConstraint("staff_id", "shop_id", name="uq_user_shop"),
    )

    # ORM 關聯映射 (可選)
    shop = relationship("ShopModel", back_populates="staff_relations")  # 👈 修改這裡！
    
    # 對應 StaffModel 中的 shop_employments 屬性
    staff = relationship("StaffModel", back_populates="shop_employments")  # ✅ 正確！