"""
Pydantic schemas for scraper API endpoints
"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class ScrapeConfig(BaseModel):
    """Configuration for vehicle scraping task"""
    config_id: Optional[int] = None  # For selecting from dropdown
    target_url: Optional[str] = None  # Direct URL override
    headers: Optional[dict] = None
    timeout: Optional[int] = 10

class ScraperConfigResponse(BaseModel):
    """Response model for listing scraper configurations"""
    id: int
    name: str
    target_url: str
    is_active: bool
    created_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class ScraperConfigDetailResponse(BaseModel):
    """Detailed response for a specific scraper configuration"""
    id: int
    name: str
    target_url: str
    headers: Optional[dict] = None
    timeout: int
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class ScraperConfigCreate(BaseModel):
    """Request model for creating a new scraper configuration"""
    name: str = Field(..., max_length=100, description="Configuration display name")
    target_url: str = Field(..., max_length=500, description="Target URL to scrape")
    headers: Optional[dict] = Field(None, description="HTTP headers as key-value pairs")
    timeout: int = Field(default=10, ge=5, le=60, description="Request timeout in seconds (5-60)")

class ScraperConfigUpdate(BaseModel):
    """Request model for updating a scraper configuration"""
    name: Optional[str] = Field(None, max_length=100, description="Configuration display name")
    target_url: Optional[str] = Field(None, max_length=500, description="Target URL to scrape")
    headers: Optional[dict] = Field(None, description="HTTP headers as key-value pairs")
    timeout: Optional[int] = Field(None, ge=5, le=60, description="Request timeout in seconds (5-60)")
    is_active: Optional[bool] = Field(None, description="Whether this config is active")

class ExecuteScrapeRequest(BaseModel):
    """Request model for executing a scrape with selected configuration"""
    config_id: int = Field(..., description="ID of the scraper configuration to execute")
