# src/core/shop_agent/models.py
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime

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
    in_stock_time = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


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

# ==========================================
# 1. 合作伙伴/客户模型 (Partner)
# ==========================================
class Partner(Base):
    """往来单位表（客户/供应商）"""
    __tablename__ = "partner"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(50), nullable=False, comment="姓名/单位名称")
    phone = Column(String(20), default=None, nullable=True, comment="联系电话")
    type = Column(SmallInteger, nullable=False, default=1, comment="类型：1-客户 2-供应商 3-二者皆是")
    receivable_amount = Column(Numeric(10, 2), nullable=False, default=0.00, comment="当前应收款金额(元)")
    payable_amount = Column(Numeric(10, 2), nullable=False, default=0.00, comment="当前应付款金额(元)")
    remark = Column(String(255), default=None, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now(), 
        comment="更新时间"
    )

    # 索引定义 (匹配你 DDL 中的 CREATE INDEX)
    __table_args__ = (
        Index("idx_partner_phone", "phone"),
        Index("idx_partner_type", "type"),
    )
