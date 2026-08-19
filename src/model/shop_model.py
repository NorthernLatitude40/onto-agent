# src/model/shop_model.py (或直接加在 src/model/models.py 中)

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from src.common.database import Base  # 你的 Base基类

class ShopModel(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    logo = Column(String(255), nullable=True, comment="店铺LOGO图片地址")
    contact_name = Column(String(50), nullable=True, comment="联系人姓名")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")
    province = Column(String(50), nullable=True, comment="省/地区")
    city = Column(String(50), nullable=True, comment="城市")
    district = Column(String(50), nullable=True, comment="区县")
    address_detail = Column(String(255), nullable=True, comment="详细地址")
    is_active = Column(Boolean, default=True, comment="店铺状态：1-正常，0-禁用")

    # 1个店铺对应多个 staff 记录
    staffs = relationship("StaffModel", back_populates="shop", cascade="all, delete-orphan")

    inventories = relationship("InventoryModel", back_populates="shop", cascade="all, delete-orphan")

    partners = relationship("Partner", back_populates="shop", cascade="all, delete-orphan")