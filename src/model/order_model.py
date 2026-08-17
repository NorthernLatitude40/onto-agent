from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime

# ==========================================
# 出库/销售订单主表 (outbound_order)
# ==========================================
class OutboundOrder(Base):
    __tablename__ = 'outbound_order'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_sn = Column(String(64), unique=True, nullable=False)
    customer_id = Column(BigInteger, ForeignKey('partner.id', ondelete='SET NULL'), nullable=True)
    outbound_type = Column(Integer, nullable=False, default=1) # 1-手机出库 2-配件出库
    total_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    total_profit = Column(Numeric(10, 2), nullable=False, default=0.00)
    payment_status = Column(Integer, nullable=False, default=1) # 1-已全额 2-挂账 3-未付
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    shop_id = Column(
            Integer, 
            ForeignKey("shops.id", ondelete="CASCADE"), 
            nullable=False, 
            index=True, 
            comment="所属店铺ID"
        )