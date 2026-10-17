"""
Pydantic schemas for scraper API endpoints
"""
from typing import Optional, List, Literal, Union
from pydantic import BaseModel, Field, ConfigDict

# Step mode types
StepMode = Literal["api", "browser"]
ParserType = Literal["jsonpath", "css_selector", "xpath", "regex"]

class ParsingRule(BaseModel):
    """Data parsing rule with multiple parser support"""
    id: Optional[str] = None
    name: str = Field(..., max_length=100, description="Rule display name")
    jsonpath: Optional[str] = Field(None, description="JSONPath expression (optional)")
    css_selector: Optional[str] = Field(None, description="CSS selector (optional)")
    xpath: Optional[str] = Field(None, description="XPath expression (optional)")
    regex: Optional[str] = Field(None, description="Regex pattern (optional)")
    output_field: str = Field(..., max_length=100, description="Target field name in result")
    required: bool = Field(default=False, description="Whether this rule is mandatory")

class ScraperStep(BaseModel):
    """Individual step in a scraper workflow with independent mode"""
    id: str = Field(..., max_length=50, description="Unique step identifier")
    name: str = Field(..., max_length=100, description="Step display name")
    mode: StepMode = Field(default="api", description="Step execution mode: 'api' or 'browser'")
    url: str = Field(..., max_length=500, description="Target URL for this step")
    method: Literal["GET", "POST", "PUT", "DELETE"] = Field(default="GET", description="HTTP method")
    params_json: Optional[str] = Field(None, description="Request parameters as JSON string")
    headers_json: Optional[str] = Field(None, description="Headers as JSON string")
    parsing_rules: List[ParsingRule] = Field(default_factory=list, description="List of parsing rules for this step")
    delay: Optional[int] = Field(None, ge=0, le=60000, description="Delay in milliseconds before executing this step (0-60000)")
    retry_count: Optional[int] = Field(None, ge=1, le=10, description="Number of retries if step fails (1-10)")

class ScrapeConfig(BaseModel):
    """Configuration for vehicle scraping task"""
    config_id: Optional[int] = None  # For selecting from dropdown
    target_url: Optional[str] = None  # Direct URL override (legacy format)
    headers: Optional[dict] = None
    timeout: Optional[int] = 10

class ScraperConfigResponse(BaseModel):
    """Response model for listing scraper configurations"""
    id: int
    name: str
    target_url: str
    is_active: bool
    mode: str  # Legacy global mode field
    created_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class ScraperConfigDetailResponse(BaseModel):
    """Detailed response for a specific scraper configuration"""
    id: int
    name: str
    target_url: str  # Legacy format
    headers: Optional[dict] = None
    timeout: int
    is_active: bool
    mode: str  # Legacy global mode field
    steps: Optional[List[ScraperStep]] = Field(None, description="Array of step configurations (new format)")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class ScraperConfigCreate(BaseModel):
    """Request model for creating a new scraper configuration"""
    name: str = Field(..., max_length=100, description="Configuration display name")
    target_url: Optional[str] = Field(None, max_length=500, description="Target URL to scrape (legacy format)")
    headers: Optional[dict] = Field(None, description="HTTP headers as key-value pairs")
    timeout: int = Field(default=10, ge=5, le=60, description="Request timeout in seconds (5-60)")
    mode: str = Field(default="api", pattern="^(html|api|playwright)$", description="Scraping mode: 'html', 'api', or 'playwright' (legacy global mode)")
    steps: Optional[List[ScraperStep]] = Field(None, description="Array of step configurations with individual modes (new format)")

class ScraperConfigUpdate(BaseModel):
    """Request model for updating a scraper configuration"""
    name: Optional[str] = Field(None, max_length=100, description="Configuration display name")
    target_url: Optional[str] = Field(None, max_length=500, description="Target URL to scrape (legacy format)")
    headers: Optional[dict] = Field(None, description="HTTP headers as key-value pairs")
    timeout: Optional[int] = Field(None, ge=5, le=60, description="Request timeout in seconds (5-60)")
    is_active: Optional[bool] = Field(None, description="Whether this config is active")
    mode: Optional[str] = Field(None, pattern="^(html|api|playwright)$", description="Scraping mode: 'html', 'api', or 'playwright' (legacy global mode)")
    steps: Optional[List[ScraperStep]] = Field(None, description="Array of step configurations with individual modes (new format)")

class ExecuteScrapeRequest(BaseModel):
    """Request model for executing a scrape with selected configuration"""
    config_id: int = Field(..., description="ID of the scraper configuration to execute")
    mode: Optional[str] = Field(None, description="Override scraping mode (html/api/playwright) - legacy global override")
