from sqlalchemy import Column, BigInteger, String, SmallInteger, Numeric, DateTime, Text, func
from src.common.database import Base

class OutboundOrderModel(Base):
    __tablename__ = "outbound_order"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主鍵 ID")
    order_sn = Column(String(64), nullable=False, unique=True, comment="出貨單號")
    customer_id = Column(BigInteger, nullable=True, comment="客戶 ID")
    outbound_type = Column(SmallInteger, nullable=False, default=1, comment="出貨類型: 1-零售, 2-批發")
    total_amount = Column(Numeric(10, 2), nullable=False, default=0.00, comment="總金額")
    total_profit = Column(Numeric(10, 2), nullable=False, default=0.00, comment="總利潤")
    payment_status = Column(SmallInteger, nullable=False, default=1, comment="狀態: 1-待出庫, 2-已完成")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="建立時間")
    shop_id = Column(BigInteger, nullable=False, default=0, comment="門店 ID")
    created_by = Column(BigInteger, nullable=True, comment="操作員工 ID")
    remark = Column(Text, nullable=True, comment="備註")