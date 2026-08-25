from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# 3. Pydantic Schemas
class DictCreate(BaseModel):
    attr_type: str
    attr_value: str
    sort_order: Optional[int] = 0

class DictResponse(BaseModel):
    id: int
    attr_type: str
    attr_value: str
    sort_order: int

    class Config:
        from_attributes = True

# 屬性明細響應模型
class AttributeItemResponse(BaseModel):
    id: int
    model_id: Optional[int] = None
    attr_type: str
    attr_value: str
    sort_order: int

# 前端按類型分組返回的模型 (方便前端渲染下拉選單/標籤)
class AttributeGroupResponse(BaseModel):
    attr_type: str
    values: List[AttributeItemResponse]

# 新增屬性值的請求體
class AttributeCreate(BaseModel):
    attr_type: str = Field(..., example="storage", description="屬性類型 (如 color, storage, version)")
    attr_value: str = Field(..., example="1TB", description="屬性值 (如 128GB, 星光色)")
    sort_order: Optional[int] = Field(0, description="排序")
