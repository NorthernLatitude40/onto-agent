"""
Enhanced Pydantic models for scraper steps and parsing rules
with proper separation of concerns and mutual exclusion support.
"""
from typing import Literal, Union, Dict, Any, Optional, List
from pydantic import BaseModel, Field

# =============================================================================
# PARSING RULE MODELS - Mutual Exclusion Support
# =============================================================================

class JsonPathRule(BaseModel):
    """JSONPath parsing rule for JSON responses"""
    rule_type: Literal["json_path"] = "json_path"
    expression: str = Field(..., description="JSONPath expression, e.g., $.vehicle.name")

class CssSelectorRule(BaseModel):
    """CSS Selector parsing rule for HTML content"""
    rule_type: Literal["css_selector"] = "css_selector"
    expression: str = Field(..., description="CSS selector expression")

class XpathRule(BaseModel):
    """XPath parsing rule for XML/HTML documents"""
    rule_type: Literal["xpath"] = "xpath"
    expression: str = Field(..., description="XPath expression")

class RegexRule(BaseModel):
    """Regular expression parsing rule for text extraction"""
    rule_type: Literal["regex"] = "regex"
    expression: str = Field(..., description="Regular expression pattern")
    flags: Optional[str] = Field(None, description="Regex flags (e.g., 'multiline')")

class JsonSchemaRule(BaseModel):
    """JSON Schema validation and extraction rule"""
    rule_type: Literal["json_schema"] = "json_schema"
    schema_definition: Dict[str, Any] = Field(..., description="JSON Schema definition")
    extract_path: Optional[str] = Field(None, description="Path to extract from validated data")

# Union type for all parsing rules (mutually exclusive)
ParsingRule = Union[
    JsonPathRule,
    CssSelectorRule,
    XpathRule,
    RegexRule,
    JsonSchemaRule
]

# =============================================================================
# STEP ACTION MODELS - Separation of Concerns
# =============================================================================

class ApiStepConfig(BaseModel):
    """Configuration for API-based scraping steps"""
    action_type: Literal["api"] = "api"
    url: str = Field(..., description="API endpoint URL")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    headers: Optional[Dict[str, Any]] = Field(None, description="HTTP headers")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body for POST/PUT/PATCH")

class PlaywrightStepConfig(BaseModel):
    """Configuration for Playwright-based scraping steps"""
    action_type: Literal["playwright"] = "playwright"
    url: str = Field(..., description="URL to navigate to")
    wait_for_selector: Optional[str] = Field(None, description="CSS selector to wait for")
    click_selectors: Optional[List[str]] = Field(None, description="Sequence of CSS selectors to click")
    scroll_to_bottom: Optional[bool] = Field(False, description="Whether to scroll to bottom")

class StaticHtmlStepConfig(BaseModel):
    """Configuration for static HTML scraping steps"""
    action_type: Literal["static_html"] = "static_html"
    url: str = Field(..., description="URL to fetch HTML from")
    encoding: Optional[str] = Field("utf-8", description="Character encoding")

# Union type for all step action configurations
StepActionConfig = Union[
    ApiStepConfig,
    PlaywrightStepConfig,
    StaticHtmlStepConfig
]

# =============================================================================
# CORE STEP MODEL - Combines Action + Parsing Rules
# =============================================================================

class ScraperStep(BaseModel):
    """
    Enhanced scraper step model with clear separation between:
    1. Step execution action (what to do)
    2. Data parsing rules (how to extract data)

    The parsing_rules field is a single object (not list) and supports
    mutually exclusive rule types.
    """
    step_name: str = Field(..., max_length=100, description="Human-readable step name")
    action_config: StepActionConfig = Field(..., description="Step execution configuration")

    # Single parsing rule object (mutually exclusive types)
    parsing_rules: Optional[ParsingRule] = Field(
        None,
        description="Single parsing rule for data extraction (mutually exclusive types)"
    )

    # Common step settings
    delay: Optional[int] = Field(
        None,
        ge=0,
        le=60000,
        description="Delay in milliseconds before executing this step"
    )
    retry_count: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Number of retries if step fails"
    )

    # Step metadata
    description: Optional[str] = Field(None, description="Step description for documentation")
    is_active: bool = Field(default=True, description="Whether this step is enabled")

# =============================================================================
# BACKWARD COMPATIBILITY MODELS
# =============================================================================

class LegacyScraperStep(BaseModel):
    """
    Backward compatibility model that maps to the existing database schema.
    This maintains compatibility with existing code while providing migration path.
    """
    step_name: str = Field(..., max_length=100)
    scrape_mode: Literal["api", "browser", "html", "playwright"] = "api"
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE"] = "GET"
    params: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = 10
    is_active: bool = True

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_parsing_rule_type(rule: ParsingRule) -> str:
    """Get the type of a parsing rule"""
    return rule.rule_type

def get_step_action_type(step: ScraperStep) -> str:
    """Get the action type from a step configuration"""
    return step.action_config.action_type