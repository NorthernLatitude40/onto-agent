from sqlalchemy import Column, BigInteger, String, Numeric, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

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
    status = Column(BigInteger, default=1)
    
    # 💡 新增/补充 shop_id 关联字段：
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False, index=True, comment="所属店铺ID")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    in_stock_time = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())