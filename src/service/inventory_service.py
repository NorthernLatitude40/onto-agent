# src/services/inventory_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from src.model.inventory_model import InventoryModel

class InventoryService:
    staticmethod
    def get_stock_count(db: Session, categories: list | None = None) -> int:
        """
        获取在库设备总台数 (用于首页看板)
        """
        if categories is None:
            categories = [1, 2]

        # 🌟 修改点：直接使用 .count() 统计符合条件的设备条数（台数）
        return db.query(InventoryModel)\
                 .filter(InventoryModel.status == 1)\
                 .filter(InventoryModel.category.in_(categories))\
                 .count() or 0

    @staticmethod
    def query_stock_items(db: Session, shop_id: int, keyword: str = "", status: int = 1):
        """
        核心查库逻辑：供 API 和 Agent Tools 共同复用
        """
        query = db.query(InventoryModel).filter(InventoryModel.status == status)
        
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    InventoryModel.title.ilike(kw),
                    InventoryModel.spec.ilike(kw),
                    InventoryModel.remark.ilike(kw),
                    InventoryModel.shop_id == shop_id
                )
            )
        return query.order_by(InventoryModel.id.desc()).all()