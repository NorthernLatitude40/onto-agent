from sqlalchemy import Column, BigInteger, String, Numeric, Integer, DateTime, ForeignKey, func, Enum as SQLEnum, SmallInteger, Boolean
from sqlalchemy.orm import relationship
from src.common.database import Base
from src.common.dict import StockStatusEnum

class InventoryModel(Base):
    __tablename__ = "inventory"

    # 基礎欄位
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主鍵ID (自動遞增)")
    sn_code = Column(String(100), unique=True, nullable=True, comment="序列號/SN碼/IMEI碼 (唯一標識)")
    title = Column(String(100), nullable=False, comment="設備/商品名稱或標題")
    category = Column(SmallInteger, nullable=False, default=2, comment="分類類型 (如 1:新機, 2:二手機)")
    spec = Column(String(100), nullable=True, comment="規格描述/配置 (如: 256GB/深空灰)")
    purchase_price = Column(Numeric(10, 2), nullable=False, default=0.00, comment="回收/採購成本價 (元)")
    selling_price = Column(Numeric(10, 2), nullable=False, default=0.00, comment="預售/標價/出貨指導價 (元)")
    stock_quantity = Column(Integer, nullable=False, default=1, comment="庫存數量")
    status = Column(
        SmallInteger,
        nullable=False,
        default=StockStatusEnum.IN_STOCK.value,
        comment="庫存狀態 (如 0:已退貨, 1/2:在庫, 3:已售出, 4:鎖定, 5:報廢)"
    )
    supplier_id = Column(BigInteger, nullable=True, comment="關聯供應商/回收來源ID")
    in_stock_time = Column(DateTime(timezone=True), server_default=func.now(), comment="設備實際入庫/收貨時間")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="記錄創建時間")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="記錄最近更新時間")
    remark = Column(String(255), nullable=True, comment="備註說明")
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False, index=True, comment="所屬店鋪ID")
    created_by = Column(BigInteger, nullable=True, comment="創建人ID")

    # 📱 補充的二手機詳細屬性欄位 (17 ~ 26)
    condition = Column(String(32), nullable=True, comment="成色 (例: 8新, 99新)")
    color = Column(String(32), nullable=True, comment="顏色 (例: 午夜色)")
    storage = Column(String(32), nullable=True, comment="內存 (例: 256GB)")
    version = Column(String(64), nullable=True, comment="版本 (例: 大陸國行)")
    battery = Column(String(16), nullable=True, comment="電池健康值 (例: 77%)")
    system_version = Column(String(64), nullable=True, comment="系統版本 (例: iOS 16.5)")
    network = Column(String(64), nullable=True, comment="網絡類型 (例: 全網通 5G)")
    condition_detail = Column(String(255), nullable=True, comment="機況細節 (例: 無拆修)")
    imei = Column(String(64), nullable=True, comment="IMEI 碼")
    is_outof_warranty = Column(Boolean, default=True, comment="是否已過保 (true-是, false-否)")

    # 關聯關係
    shop = relationship("ShopModel", back_populates="inventories")