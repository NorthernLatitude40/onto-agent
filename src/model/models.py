# src/core/shop_agent/models.py
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime

class FinancialRecord(Base):
    __tablename__ = "financial_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_sn = Column(String(64), nullable=False, unique=True)
    type = Column(SmallInteger, nullable=False) # 1-收入 2-支出
    category = Column(String(50), nullable=False)
    business_type = Column(SmallInteger, default=0) 
    business_id = Column(BigInteger, nullable=True)
    partner_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False, default=0.00) # 交易金额
    profit = Column(Numeric(10, 2), nullable=False, default=0.00) # 毛利
    payment_method = Column(String(30), default="微信")
    record_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    remark = Column(String(255), nullable=True)
    # 💡 补上 shop_id 字段定义
    shop_id = Column(
        Integer, 
        ForeignKey("shops.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True, 
        comment="所属店铺ID"
    )
    device_sn_code = Column(String(64), nullable=False, unique=True)




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

