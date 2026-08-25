from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request, Path, FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.common.database import get_db
from src.model.dict_schema import DictCreate,  DictResponse
from src.model.device_models import DeviceModelAttribute, DeviceModel




# 4. FastAPI 實例
router = APIRouter()
# --- 接口 API ---

# A. 查詢通用字典列表 (model_id IS NULL)
@router.get("", response_model=List[DictResponse])
def get_dictionaries(
    attr_type: str = Query(..., description="字典類型 (如: condition, network, condition_detail)"),
    db: Session = Depends(get_db)
):
    items = db.query(DeviceModelAttribute).filter(
        DeviceModelAttribute.model_id.is_(None),
        DeviceModelAttribute.attr_type == attr_type
    ).order_by(DeviceModelAttribute.sort_order.asc(), DeviceModelAttribute.id.asc()).all()
    
    return items

# B. 新增通用字典項
@router.post("", response_model=DictResponse)
def create_dictionary(item: DictCreate, db: Session = Depends(get_db)):
    # 檢查是否已存在相同的通用標籤
    exists = db.query(DeviceModelAttribute).filter(
        DeviceModelAttribute.model_id.is_(None),
        DeviceModelAttribute.attr_type == item.attr_type,
        DeviceModelAttribute.attr_value == item.attr_value
    ).first()
    
    if exists:
        raise HTTPException(status_code=400, detail="該字典標籤已存在")

    new_item = DeviceModelAttribute(
        model_id=None,  # 強制為 None，代表通用字典
        attr_type=item.attr_type,
        attr_value=item.attr_value,
        sort_order=item.sort_order
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

# C. 刪除通用字典項
@router.delete("/{attr_id}")
def delete_dictionary(attr_id: int, db: Session = Depends(get_db)):
    target = db.query(DeviceModelAttribute).filter(
        DeviceModelAttribute.id == attr_id,
        DeviceModelAttribute.model_id.is_(None)
    ).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="該標籤不存在或不可刪除")
    
    db.delete(target)
    db.commit()
    return {"message": "刪除成功"}