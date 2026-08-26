from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request, Path, FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, Session

from src.common.database import get_db, get_db_async
from src.model.dict_schema import DictCreate,  DictResponse, AttributeItemResponse, AttributeCreate
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


from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import Session

# Schemas
class ModelCreate(BaseModel):
    brand: str = "Apple"
    model_name: str
    sort_order: Optional[int] = 0

class ModelResponse(BaseModel):
    id: int
    brand: str
    model_name: str
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True

# --- API 接口 ---

# 1. 獲取機型列表 (可按品牌過濾)
@router.get("/device-models", response_model=List[ModelResponse])
def get_device_models(
    brand: Optional[str] = Query(None, description="品牌名稱，如 Apple"),
    db: Session = Depends(get_db)
):
    query = db.query(DeviceModel)
    if brand:
        query = query.filter(DeviceModel.brand == brand)
    return query.order_by(DeviceModel.sort_order.asc(), DeviceModel.id.desc()).all()

# 2. 新增機型 (SPU)
@router.post("/device-models", response_model=ModelResponse)
def create_device_model(item: ModelCreate, db: Session = Depends(get_db)):
    exists = db.query(DeviceModel).filter(
        DeviceModel.brand == item.brand,
        DeviceModel.model_name == item.model_name
    ).first()
    
    if exists:
        raise HTTPException(status_code=400, detail="該品牌下已存在此機型名稱")

    new_model = DeviceModel(
        brand=item.brand,
        model_name=item.model_name.strip(),
        sort_order=item.sort_order,
        is_active=True
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    return new_model

# 3. 刪除或下架機型
@router.delete("/device-models/{model_id}")
def delete_device_model(model_id: int, db: Session = Depends(get_db)):
    target = db.query(DeviceModel).filter(DeviceModel.id == model_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="機型不存在")
    
    db.delete(target)
    db.commit()
    return {"message": "機型已成功刪除"}

@router.get("/device-models/brands")
def get_brands(db: Session = Depends(get_db)):
    # 查詢現有所有品牌，並按字母排序
    brands = db.query(DeviceModel.brand).distinct().all()
    brand_list = [b[0] for b in brands if b[0]]
    
    # 保證 Apple 始終在第一個，其餘排序
    if "Apple" in brand_list:
        brand_list.remove("Apple")
        brand_list.insert(0, "Apple")
        
    return brand_list

# ==================== 新增機型專屬屬性 ====================
@router.post(
    "/device-models/{model_id}/attributes",
    response_model=AttributeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="為指定機型新增屬性"
)
async def create_model_attribute(
    model_id: int, 
    payload: AttributeCreate, 
    db: AsyncSession = Depends(get_db_async)
):
    """
    為指定 model_id 插入一條新的屬性記錄 (如: model_id=2, attr_type='storage', attr_value='1TB')
    """
    # 1. 檢查主表機型是否存在 (先 await db.execute，再取 scalar)
    model_check = await db.execute(
        select(DeviceModel.id).where(DeviceModel.id == model_id)
    )
    if not model_check.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"機型 ID {model_id} 不存在"
        )

    # 2. 檢查該機型下是否已存在相同的 attr_type 和 attr_value
    stmt = select(DeviceModelAttribute).where(
        DeviceModelAttribute.model_id == model_id,
        DeviceModelAttribute.attr_type == payload.attr_type,
        DeviceModelAttribute.attr_value == payload.attr_value
    )
    result = await db.execute(stmt)
    existing_attr = result.scalar_one_or_none()

    if existing_attr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"機型已存在屬性: {payload.attr_type} = {payload.attr_value}"
        )

    # 3. 創建並插入數據庫
    new_attr = DeviceModelAttribute(
        model_id=model_id,
        attr_type=payload.attr_type,
        attr_value=payload.attr_value,
        sort_order=payload.sort_order if payload.sort_order is not None else 0
    )
    
    db.add(new_attr)
    await db.commit()
    await db.refresh(new_attr)  # 刷新獲取數據庫生成的自增 id

    return new_attr


# ==================== 獲取機型專有屬性 ====================
@router.get(
    "/device-models/{model_id}/attributes",
    response_model=List[AttributeItemResponse],
    summary="獲取指定機型的專有屬性（支持按 attr_type 篩選）"
)
async def get_model_attributes(
    model_id: int,
    attr_type: Optional[str] = Query(None, description="屬性類型，例如: version, color, storage"),
    db: AsyncSession = Depends(get_db_async)
):
    """
    僅查詢指定機型 (model_id) 的專有屬性，不包含通用屬性。
    若傳入 attr_type 參數，則只返回該類型的屬性。
    """
    # 1. 僅匹配指定機型 ID
    stmt = select(DeviceModelAttribute).where(
        DeviceModelAttribute.model_id == model_id
    )

    # 2. 如果前端傳了 attr_type，增加篩選條件
    if attr_type:
        stmt = stmt.where(DeviceModelAttribute.attr_type == attr_type)

    # 3. 排序：按 attr_type 及 sort_order 升序
    stmt = stmt.order_by(
        DeviceModelAttribute.attr_type.asc(),
        DeviceModelAttribute.sort_order.asc()
    )

    # 4. 執行非同步查詢
    result = await db.scalars(stmt)
    attributes = result.all()

    return attributes

@router.delete(
    "/attributes/{attr_id}",
    status_code=status.HTTP_200_OK,
    summary="刪除指定 ID 的屬性記錄"
)
async def delete_attribute(
    attr_id: int,
    db: AsyncSession = Depends(get_db_async)
):
    """
    根據屬性主鍵 ID (id) 刪除該條屬性記錄
    """
    # 1. 查詢目標屬性記錄是否存在
    stmt = select(DeviceModelAttribute).where(DeviceModelAttribute.id == attr_id)
    result = await db.scalars(stmt)
    target_attr = result.first()

    if not target_attr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到 ID 為 {attr_id} 的屬性"
        )

    # 2. 執行刪除並提交
    await db.delete(target_attr)
    await db.commit()

    return {"message": f"屬性 ID {attr_id} 已成功刪除", "id": attr_id}