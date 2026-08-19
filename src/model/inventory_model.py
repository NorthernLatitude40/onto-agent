from sqlalchemy import Column, BigInteger, String, Numeric, Integer, DateTime, ForeignKey, func, Enum as SQLEnum, SmallInteger
from sqlalchemy.orm import relationship
from src.common.database import Base
from src.common.dict import InventoryStatusEnum

class InventoryModel(Base):
    __tablename__ = "inventory"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sn_code = Column(String(100), unique=True)
    title = Column(String(100), nullable=False)
    purchase_price = Column(Numeric(10, 2), nullable=False, default=0.00)
    selling_price = Column(Numeric(10, 2), nullable=False, default=0.00)
    spec = Column(String(100), nullable=True)
    remark = Column(String(255), nullable=True)
    category = Column(BigInteger, default=2)
    stock_quantity = Column(Integer, nullable=False, default=1)
    status = Column(
        SmallInteger,
        default=InventoryStatusEnum.IN_STOCK.value,
        comment="設備狀態: 1-在庫, 2-已售出, 3-鎖定, 4-退貨, 5-報廢"
    )
    created_by = Column(BigInteger, nullable=True)
    supplier_id = Column(BigInteger, nullable=True)
    
    # 💡 新增/补充 shop_id 关联字段：
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False, index=True, comment="所属店铺ID")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    in_stock_time = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    shop = relationship("ShopModel", back_populates="inventories")