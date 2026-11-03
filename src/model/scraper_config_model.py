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
    
    Supports both legacy format (target_url, step2_url, etc.) and new
    step-level format (steps JSON array) for backward compatibility.
    """
    __tablename__ = "scraper_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="Configuration name for display")
    target_url = Column(String(500), nullable=False, comment="Target URL to scrape (legacy format)")
    headers = Column(JSON, nullable=True, comment="HTTP headers as JSON")
    timeout = Column(Integer, default=10, comment="Request timeout in seconds")
    is_active = Column(Boolean, default=True, comment="Whether this config is active")
    mode = Column(String(20), default="api", comment="Scraping mode: 'html', 'api', or 'playwright' (legacy)")
    step2_url = Column(String(500), nullable=True, comment="Step 2 API endpoint URL (legacy format)")
    step3_url = Column(String(500), nullable=True, comment="Step 3 API endpoint URL (legacy format)")
    calctotal_url = Column(String(500), nullable=True, comment="CalcTotal API endpoint URL (legacy format)")
    common_params = Column(JSON, nullable=True, comment="Common request parameters as JSON")
    steps = Column(JSON, nullable=True, comment="""
        Array of step configurations for sequential API requests.
        Each step contains:
        {
            "step_name": string,           # Display name (e.g., "初始请求")
            "scrape_mode": string,         # 'api' or 'html' or 'playwright'
            "url": string,                 # Request URL
            "method": string,              # HTTP method (GET, POST, etc.)
            "params": object,              # Request parameters as JSON
            "headers": object,             # Custom headers as JSON
            "timeout": integer,            # Timeout in seconds
            "is_active": boolean           # Whether this step is enabled
        }
    """)
    created_at = Column(DateTime, server_default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    
    # Configurable parameters for the _scrape_with_requests method
    base_url = Column(String(512), nullable=False, comment="Base URL for vehicle listings page")
    api_endpoint = Column(String(512), nullable=False, comment="API endpoint for individual vehicle details")
    calc_total_endpoint = Column(String(512), nullable=False, comment="API endpoint for calculating total vehicles")
    default_params = Column(JSON, default={}, comment="Default request parameters (sort_order, page_size)")
    sort_order = Column(String(64), default='desc', comment="Sort order for vehicle listings (asc/desc)")
    page_size = Column(Integer, default=20, comment="Number of vehicles per page")
    vehicle_type = Column(String(64), comment="Filter by vehicle type (e.g., 'campervan')")
