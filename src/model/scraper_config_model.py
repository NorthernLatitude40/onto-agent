"""
Database model for storing scraper configurations
"""
from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, func
from src.common.database import Base

class ScraperConfigModel(Base):
    """
    SQLAlchemy model for storing scrape configurations.
    
    This table stores configuration settings for different scraping targets,
    allowing users to select from a dropdown list and execute scrapes.
    """
    __tablename__ = "scraper_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="Configuration name for display")
    target_url = Column(String(500), nullable=False, comment="Target URL to scrape")
    headers = Column(JSON, nullable=True, comment="HTTP headers as JSON")
    timeout = Column(Integer, default=10, comment="Request timeout in seconds")
    is_active = Column(Boolean, default=True, comment="Whether this config is active")
    created_at = Column(DateTime, server_default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Last update timestamp")
