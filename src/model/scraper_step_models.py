"""
Enhanced Pydantic models for scraper steps and parsing rules
with proper separation of concerns and mutual exclusion support.
"""
from typing import Literal, Union, Dict, Any, Optional, List
from pydantic import BaseModel, Field, model_validator

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
    
    @classmethod
    def from_frontend_data(cls, data: Dict[str, Any]) -> 'PlaywrightStepConfig':
        """
        Convert frontend Playwright step configuration to backend model.
        Handles field name mapping between frontend and backend.
        """
        # Map frontend field names to backend field names
        mapped_data = {}
        
        # url -> target_url (frontend) or url (backend)
        if 'target_url' in data and 'url' not in data:
            mapped_data['url'] = data['target_url']
        elif 'url' in data:
            mapped_data['url'] = data['url']
            
        # wait_for_selector -> wait_selector (frontend) or wait_for_selector (backend)
        if 'wait_selector' in data and 'wait_for_selector' not in data:
            mapped_data['wait_for_selector'] = data['wait_selector']
        elif 'wait_for_selector' in data:
            mapped_data['wait_for_selector'] = data['wait_for_selector']
        
        # Preserve all other frontend fields that match backend field names
        for key, value in data.items():
            if key not in mapped_data and hasattr(cls, key):
                mapped_data[key] = value
        
        return cls(**mapped_data)

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

    @model_validator(mode='before')
    @classmethod
    def validate_step_format(cls, data):
        """
        Custom validator that handles both legacy and new step formats.
        
        Legacy format (old frontend):
        - mode field indicates the type
        - target_url, method, params_json, headers_json fields
        
        New format (new frontend):
        - action_config field with proper structure
        """
        if isinstance(data, dict) and 'mode' in data:
            # Legacy format - convert to new format using the adapter function
            converted = create_step_from_legacy_data(data)
            # Return as dict for further validation
            return converted.model_dump()
        elif isinstance(data, dict) and 'action_config' in data and isinstance(data['action_config'], dict):
            # New format with action_config - apply field name mapping if needed
            action_config = data['action_config']
            
            # Check if this looks like frontend data (has target_url or wait_selector)
            has_frontend_fields = (
                'target_url' in action_config or
                'wait_selector' in action_config or
                'script' in action_config
            )
            
            if has_frontend_fields and action_config.get('action_type') == 'playwright':
                # Convert frontend field names to backend field names for Playwright config
                converted_action_config = PlaywrightStepConfig.from_frontend_data(action_config)
                data['action_config'] = converted_action_config.model_dump()
        
        return data

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

def create_step_from_legacy_data(data: Dict[str, Any]) -> ScraperStep:
    """
    Create a ScraperStep from legacy frontend data format.
    Handles field name mapping and conversion for backward compatibility.
    """
    # Determine action type based on mode
    mode = data.get('mode', 'api')
    
    if mode == 'playwright':
        # Create PlaywrightStepConfig with proper field mapping
        playwright_data = {
            'action_type': 'playwright',
            'url': data.get('target_url', data.get('url', '')),
            'wait_for_selector': data.get('wait_selector', data.get('wait_for_selector')),
        }
        
        # Copy additional Playwright-specific fields if they exist
        playwright_fields = ['script', 'playwright_headers', 'proxy', 'timeout', 'user_agent', 'viewport']
        for field in playwright_fields:
            if field in data:
                playwright_data[field] = data[field]
        
        action_config = PlaywrightStepConfig(**playwright_data)
    elif mode == 'api':
        # Create ApiStepConfig
        api_data = {
            'action_type': 'api',
            'url': data.get('target_url', data.get('url', '')),
            'method': data.get('method', 'GET'),
            'params': data.get('params'),
            'headers': data.get('headers'),
        }
        action_config = ApiStepConfig(**api_data)
    else:
        # Default to API mode
        api_data = {
            'action_type': 'api',
            'url': data.get('target_url', data.get('url', '')),
            'method': data.get('method', 'GET'),
        }
        action_config = ApiStepConfig(**api_data)
    
    # Create parsing rules if present
    parsing_rule = None
    if 'parsing_rules' in data:
        parsing_rule = data['parsing_rules']
    
    return ScraperStep(
        step_name=data.get('name', 'Unnamed Step'),
        action_config=action_config,
        parsing_rules=parsing_rule,
        delay=data.get('delay'),
        retry_count=data.get('retry_count'),
        description=data.get('description'),
        is_active=data.get('is_active', True)
    )