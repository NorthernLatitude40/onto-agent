from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
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