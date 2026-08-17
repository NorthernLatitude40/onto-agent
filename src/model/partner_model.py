from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index
from src.common.database import SessionLocal, Base, engine
from sqlalchemy.orm import relationship
from datetime import datetime


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
