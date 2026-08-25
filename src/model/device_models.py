from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.common.database import Base

class DeviceModel(Base):
    __tablename__ = "device_models"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    brand = Column(String(32), nullable=False, default="Apple", comment="品牌 (例: Apple, Huawei)")
    model_name = Column(String(64), nullable=False, comment="機型名稱 (例: iPhone 13)")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否啟用")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序")

    # 一對多關聯：一個機型對應多個屬性，Cascade 確保刪除機型時同步刪除屬性
    attributes = relationship(
        "DeviceModelAttribute", 
        back_populates="device_model", 
        cascade="all, delete-orphan",
        order_by="DeviceModelAttribute.sort_order"
    )

class DeviceModelAttribute(Base):
    __tablename__ = "device_model_attributes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("device_models.id", ondelete="CASCADE"), nullable=False, comment="關聯 device_models.id")
    attr_type = Column(String(32), nullable=False, comment="屬性類型: color(顏色), storage(內存), version(版本)")
    attr_value = Column(String(64), nullable=False, comment="屬性值 (例: 256GB, 午夜色)")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序")

    # 反向關聯
    device_model = relationship("DeviceModel", back_populates="attributes")