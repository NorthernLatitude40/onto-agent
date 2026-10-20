"""
SQLAlchemy model for storing crawler step configurations.

This table stores individual crawling steps that can be executed
as part of a scraper workflow. Each step represents one action
in the scraping process (e.g., API call, HTML parsing, etc.).
"""
from sqlalchemy import Column, BigInteger, String, Text, JSON, Boolean, DateTime, CheckConstraint
from sqlalchemy.sql import func
from .models import Base


class CrawlerStepsModel(Base):
    """
    SQLAlchemy model for storing crawler step configurations.
    
    This table stores individual crawling steps that can be executed
    as part of a scraper workflow. Each step represents one action
    in the scraping process (e.g., API call, HTML parsing, etc.).
    """
    __tablename__ = "crawler_steps"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    scraper_config_id = Column(BigInteger, nullable=False, comment="Foreign key to scraper_configs table")
    name = Column(String(100), nullable=False, comment="Step display name")
    target_type = Column(
        String(30),
        nullable=False,
        comment="Type of crawling target: 'api', 'html', or 'unstructured'",
    )
    target_url = Column(Text, nullable=False, comment="Target URL or endpoint to crawl")
    config = Column(
        JSON,
        nullable=False,
        default={},
        comment="Polymorphic configuration for different step types (JSON)"
    )
    enabled = Column(Boolean, nullable=False, default=True, comment="Whether this step is active")
    created_at = Column(DateTime, server_default=func.now(), comment="Creation timestamp")
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )
    
    # Constraint to ensure target_type has valid values
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('api', 'html', 'unstructured')",
            name="chk_crawler_steps_target_type"
        ),
    )