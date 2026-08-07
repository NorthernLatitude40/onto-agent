# src/core/shop_agent/models.py
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer
from src.common.database import SessionLocal, Base, engine

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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