from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime


# ==========================================
# 出库订单明细表 (outbound_order_item)
# ==========================================
class OutboundOrderItem(Base):
    __tablename__ = 'outbound_order_item'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    outbound_order_id = Column(BigInteger, ForeignKey('outbound_order.id', ondelete='CASCADE'), nullable=False)
    inventory_id = Column(BigInteger, ForeignKey('inventory.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    purchase_price = Column(Numeric(10, 2), nullable=False, default=0.00) # 成本
    selling_price = Column(Numeric(10, 2), nullable=False, default=0.00)  # 售价
    profit = Column(Numeric(10, 2), nullable=False, default=0.00)         # 毛利