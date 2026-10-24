from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from src.common.database import Base  # 請根據您的專案結構調整 Base 的引入路徑

class ScraperGroup(Base):
    __tablename__ = "scraper_groups"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ScraperGroup(id={self.id}, name='{self.name}')>"