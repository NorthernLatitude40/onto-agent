from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.api.v1.endpoints.dao.inventory_dao import PricingInventoryDAO
from src.schema.inventory import PricingInventoryCreate, PricingInventoryUpdate


class PricingInventoryService:

  @staticmethod
  def get_inventory(db: Session, inventory_id: int):
    inventory = PricingInventoryDAO.get_by_id(db, inventory_id)
    if not inventory:
      raise HTTPException(status_code=404, detail="Inventory not found")
    return inventory

  @staticmethod
  def list_inventories(db: Session, skip: int = 0, limit: int = 100):
    return PricingInventoryDAO.get_all(db, skip, limit)

  @staticmethod
  def create_inventory(db: Session, obj_in: PricingInventoryCreate):
    # 可以在这里加一些业务校验，例如检查 model_id 是否真实存在
    return PricingInventoryDAO.create(db, obj_in)

  @staticmethod
  def update_inventory(
      db: Session, inventory_id: int, obj_in: PricingInventoryUpdate
  ):
    db_obj = PricingInventoryDAO.get_by_id(db, inventory_id)
    if not db_obj:
      raise HTTPException(status_code=404, detail="Inventory not found")
    return PricingInventoryDAO.update(db, db_obj, obj_in)

  @staticmethod
  def delete_inventory(db: Session, inventory_id: int):
    db_obj = PricingInventoryDAO.get_by_id(db, inventory_id)
    if not db_obj:
      raise HTTPException(status_code=404, detail="Inventory not found")
    return PricingInventoryDAO.delete(db, inventory_id)