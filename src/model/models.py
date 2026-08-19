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
    created_by = Column(BigInteger, nullable=True)  # 👈 補上此定義
    created_at = Column(DateTime(timezone=True), server_default=func.now())
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
    # 修正點：綁定特定一次生命週期的 inventory.id
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)






