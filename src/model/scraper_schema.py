"""
Pydantic schemas for scraper API endpoints
"""
from typing import Optional, List, Literal, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# Step mode types
StepMode = Literal["api", "browser", "html", "playwright","default"]
ParserType = Literal["jsonpath", "css_selector", "xpath", "regex"]

class Mapping(BaseModel):
    """Mapping between source and target fields"""
    source_key: str = Field(..., description="Source key/path to extract from")
    target_field: str = Field(..., description="Target field name in result")

class ParsingRule(BaseModel):
    """Data parsing rule with multiple parser support"""
    id: Optional[str] = None
    name: str = Field(..., max_length=100, description="Rule display name")
    jsonpath: Optional[str] = Field(None, description="JSONPath expression (optional)")
    css_selector: Optional[str] = Field(None, description="CSS selector (optional)")
    xpath: Optional[str] = Field(None, description="XPath expression (optional)")
    regex: Optional[str] = Field(None, description="Regex pattern (optional)")
    output_field: Optional[str] = Field(None, max_length=100, description="Target field name in result")
    mappings: List[Mapping] = Field(default_factory=list, description="Array of field mappings from source to target")
    required: bool = Field(default=False, description="Whether this rule is mandatory")
    
    model_config = ConfigDict()

class ScraperStep(BaseModel):
  """Individual step in a scraper workflow with independent mode"""

  # 把它改成 Optional，預設值為 None，前端沒傳也不會報錯
  id: Optional[str] = Field(
      None, max_length=50, description="Unique step identifier"
  )
  name: str = Field(..., max_length=100, description="Step display name")
  mode: StepMode = Field(
      default="api", description="Step execution mode: 'api' or 'browser'"
  )
  target_url: str = Field(..., max_length=500, description="Target URL for this step")
  method: Literal["GET", "POST", "PUT", "DELETE"] = Field(
      default="GET", description="HTTP method"
  )
  params: Optional[Dict[str, Any]] = Field(
      None, description="Request parameters as JSON object"
  )
  headers: Optional[Dict[str, Any]] = Field(
      None, description="Headers as JSON object"
  )
  parsing_rules: Optional[Union[ParsingRule, List[ParsingRule]]] = Field(
      default=None,
      description="Single parsing rule or array of parsing rules for this step to extract target fields",
  )
  delay: Optional[int] = Field(
      None,
      ge=0,
      le=60000,
      description="Delay in milliseconds before executing this step (0-60000)",
  )
  retry_count: Optional[int] = Field(
      None,
      ge=1,
      le=10,
      description="Number of retries if step fails (1-10)",
  )
  target_model: Optional[str] = Field(
      None, max_length=50, description="Target database model ID for this step"
  )
  
  model_config = ConfigDict()

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
    
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "GetLost NZ Campervan Scraper",
                "target_url": "https://getlostinnz.co.nz/",
                "is_active": True,
                "mode": "api",
                "created_at": "2024-01-15T10:30:00.000Z"
            }
        }
    )

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
    
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore"
    )

class ScraperConfigCreate(BaseModel):
    """Request model for creating a new scraper configuration"""
    project_id: int = Field(..., description="ID of the project this config belongs to")
    name: str = Field(..., max_length=100, description="Configuration display name")
    target_url: Optional[str] = Field(None, max_length=500, description="Target URL to scrape (legacy format)")
    headers: Optional[dict] = Field(None, description="HTTP headers as key-value pairs")
    timeout: int = Field(default=10, ge=5, le=60, description="Request timeout in seconds (5-60)")
    mode: str = Field(default="api", pattern="^(html|api|playwright)$", description="Scraping mode: 'html', 'api', or 'playwright' (legacy global mode)")
    steps: Optional[List[ScraperStep]] = Field(None, description="Array of step configurations with individual modes (new format)")

class ScraperConfigUpdate(BaseModel):
    """Request model for updating a scraper configuration"""
    group_id: int = Field(..., description="ID of the project this config belongs to")
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
    parsing_rules: Optional[List[ParsingRule]] = Field(None, description="Custom parsing rules to override step-level rules")
