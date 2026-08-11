# src/model/shop_model.py (或直接加在 src/model/models.py 中)

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from src.common.database import Base  # 你的 Base基类

class ShopModel(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="店铺ID")
    name = Column(String(100), nullable=False, comment="店铺名称")
    logo = Column(String(255), nullable=True, comment="店铺LOGO图片地址")
    contact_name = Column(String(50), nullable=True, comment="联系人姓名")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")
    province = Column(String(50), nullable=True, comment="省/地区")
    city = Column(String(50), nullable=True, comment="城市")
    district = Column(String(50), nullable=True, comment="区县")
    address_detail = Column(String(255), nullable=True, comment="详细地址")
    is_active = Column(Boolean, default=True, comment="店铺状态：1-正常，0-禁用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    owner_id = Column(Integer, ForeignKey("users.id")) # 店主/创建者

    # 1对多 关联：一个店铺拥有多个员工/用户
    users = relationship("User", back_populates="shop")