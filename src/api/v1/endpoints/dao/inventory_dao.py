from datetime import datetime
from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, Session, joinedload

from src.model.pricing_inventory_model import PricingInventoryModel
from src.schema.inventory import PricingInventoryCreate, PricingInventoryUpdate


class PricingInventoryDAO:

    # ---------- 内部工具 ----------
    @staticmethod
    def _base_query(db: Session) -> Query:
        return db.query(PricingInventoryModel).options(
            joinedload(PricingInventoryModel.van_model)  # 关联加载车辆
        )

    @staticmethod
    def _apply_filters(
        query: Query,
        model_id: Optional[int] = None,
        is_available: Optional[bool] = None,
        pickup_location: Optional[str] = None,
        return_location: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Query:
        M = PricingInventoryModel
        if model_id is not None:
            query = query.filter(M.model_id == model_id)
        if is_available is not None:
            query = query.filter(M.is_available == is_available)
        if pickup_location:
            query = query.filter(M.pickup_location == pickup_location)
        if return_location:
            query = query.filter(M.return_location == return_location)
        # 时间区间：与 [start_time, end_time] 有交集的记录
        if start_time is not None:
            query = query.filter(M.end_time >= start_time)
        if end_time is not None:
            query = query.filter(M.start_time <= end_time)
        return query

    @staticmethod
    def _commit(db: Session) -> None:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise

    # ---------- 查询 ----------
    @staticmethod
    def get_by_id(db: Session, inventory_id: int) -> Optional[PricingInventoryModel]:
        return (
            PricingInventoryDAO._base_query(db)
            .filter(PricingInventoryModel.id == inventory_id)
            .first()
        )

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        **filters,
    ) -> List[PricingInventoryModel]:
        query = PricingInventoryDAO._apply_filters(
            PricingInventoryDAO._base_query(db), **filters
        )
        return (
            query.order_by(PricingInventoryModel.id)  # 保证分页稳定
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count(db: Session, **filters) -> int:
        query = PricingInventoryDAO._apply_filters(
            db.query(PricingInventoryModel), **filters
        )
        return query.count()

    # ---------- 写入 ----------
    @staticmethod
    def create(db: Session, obj_in: PricingInventoryCreate) -> PricingInventoryModel:
        db_obj = PricingInventoryModel(**obj_in.model_dump())
        db.add(db_obj)
        PricingInventoryDAO._commit(db)
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def update(
        db: Session,
        db_obj: PricingInventoryModel,
        obj_in: PricingInventoryUpdate,
    ) -> PricingInventoryModel:
        # exclude_unset=True：只更新客户端实际传入的字段
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        PricingInventoryDAO._commit(db)
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def delete(db: Session, inventory_id: int) -> Optional[PricingInventoryModel]:
        db_obj = PricingInventoryDAO.get_by_id(db, inventory_id)
        if db_obj:
            db.delete(db_obj)
            PricingInventoryDAO._commit(db)
        return db_obj