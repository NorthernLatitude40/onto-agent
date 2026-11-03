# Enhanced Scraper Step Models Documentation

## Overview

This document describes the enhanced Pydantic models for scraper steps and parsing rules, designed with clear separation of concerns and mutual exclusion support.

## Key Features

1. **Separation of Concerns**: Step actions (what to do) are completely separate from parsing rules (how to extract data)
2. **Mutual Exclusion**: Parsing rules use Union types ensuring only one rule type per step
3. **Flexible Actions**: Support for API calls, Playwright automation, and static HTML scraping
4. **Pydantic Compatibility**: Models work with both v1 and v2 using standard Field definitions
5. **Extensibility**: Easy to add new rule types or action configurations

## Model Architecture

### Parsing Rule Models (Mutual Exclusion)

| Model | Description | Example Expression |
|-------|-------------|---------------------|
| `JsonPathRule` | Extract data from JSON responses using JSONPath syntax | `$.vehicles[*].name` |
| `CssSelectorRule` | Extract elements from HTML using CSS selectors | `div.vehicle-card h2.title` |
| `XpathRule` | Extract data from XML/HTML using XPath expressions | `//vehicle/details/price` |
| `RegexRule` | Extract text patterns using regular expressions | `Price: \\$(\\d+\\.\\d{2})` |
| `JsonSchemaRule` | Validate and extract structured data using JSON Schema | `{ "type": "object", "properties": {...}}` |

### Action Configuration Models

| Model | Description | Key Features |
|-------|-------------|--------------|
| `ApiStepConfig` | Make HTTP requests to APIs | URL, method, params, headers, body support |
| `PlaywrightStepConfig` | Browser automation with Playwright | URL, selectors, navigation options |
| `StaticHtmlStepConfig` | Simple HTML page fetching | URL, encoding, basic options |

### Core Model

- **`ScraperStep`**: Combines action configuration and parsing rules
  - `step_name`: Human-readable name for the step
  - `action_config`: One of the action types (mutually exclusive)
  - `parsing_rules`: Optional parsing rule (mutually exclusive types)
  - `delay`: Milliseconds to wait between steps
  - `retry_count`: Number of retry attempts on failure
  - `description`: Optional description of the step

## Usage Examples

### Basic API Scraping Step

```python
from scraper_step_models import ScraperStep, ApiStepConfig, JsonPathRule

step = ScraperStep(
    step_name="Fetch vehicle listings",
    action_config=ApiStepConfig(
        url="https://api.example.com/vehicles",
        method="GET",
        params={"category": "campervans"}
    ),
    parsing_rules=JsonPathRule(expression="$.vehicles[*].{name: name, price: price}"),
    delay=500,
    retry_count=2
)
```

### Playwright Browser Automation

```python
from scraper_step_models import ScraperStep, PlaywrightStepConfig, CssSelectorRule

step = ScraperStep(
    step_name="Extract vehicle details",
    action_config=PlaywrightStepConfig(
        url="https://example.com/vehicles/{id}",
        wait_for_selector="#vehicle-details",
        click_selectors=["#specs-tab", "#features-tab"]
    ),
    parsing_rules=CssSelectorRule(expression=".vehicle-detail h1"),
    delay=1000
)
```

### Complete Workflow Example

```python
workflow = [
    # Step 1: Get vehicle listings from API
    ScraperStep(
        step_name="Fetch listings",
        action_config=ApiStepConfig(url="https://api.example.com/vehicles"),
        parsing_rules=JsonPathRule(expression="$.vehicles[*].id")
    ),

    # Step 2: Extract details for each vehicle using Playwright
    ScraperStep(
        step_name="Get details",
        action_config=PlaywrightStepConfig(url="https://example.com/vehicle/{id}"),
        parsing_rules=CssSelectorRule(expression=".specs-table tr")
    )
]
```

## Serialization

All models support JSON serialization and deserialization:

```python
# Serialize to JSON
import json
step_data = step.model_dump()
json_str = json.dumps(step_data)

# Deserialize from JSON
reconstructed_step = ScraperStep(**json.loads(json_str))
```

## Validation Rules

1. **Mutual Exclusion**: Only one parsing rule type can be specified per step
2. **Required Fields**: `step_name` and `action_config` are required
3. **Type Safety**: All fields are validated according to their Pydantic definitions

## Error Handling

The models provide comprehensive validation:
- Invalid JSONPath expressions will raise validation errors
- Missing required fields are caught during model creation
- Type mismatches are detected automatically

## Performance Considerations

1. **Memory Usage**: Models use efficient data structures for minimal overhead
2. **Validation Speed**: Pydantic validation is optimized for performance
3. **Serialization**: JSON serialization/deserialization is fast and reliable

## Extending the Models

To add new functionality:

```python
# Add a new parsing rule type
class CustomRule(BaseModel):
    rule_type: Literal["custom"] = "custom"
    expression: str
    custom_options: Dict[str, Any]

# Update the ParsingRule union
ParsingRule = Union[
    JsonPathRule,
    CssSelectorRule,
    XpathRule,
    RegexRule,
    JsonSchemaRule,
    CustomRule  # Add new rule type
]
```

## Migration Guide

### From Legacy Models

```python
# Old way (mixed concerns)
old_step = {
    "name": "scrape",
    "url": "https://example.com",
    "jsonpath": "$.data"
}

# New way (clear separation)
new_step = ScraperStep(
    step_name="scrape",
    action_config=StaticHtmlStepConfig(url="https://example.com"),
    parsing_rules=JsonPathRule(expression="$.data")
)
```

### From Raw Dictionaries

```python
# Convert raw dict to model
raw_data = {"step_name": "test", "action_config": {...}, "parsing_rules": {...}}
step = ScraperStep(**raw_data)

# Access validated data
print(step.step_name)  # Validated string
print(step.action_config.url)  # Validated URL
```

## Best Practices

1. **Use Descriptive Names**: Give steps meaningful names for debugging
2. **Set Appropriate Delays**: Avoid overwhelming target servers
3. **Add Retry Logic**: Use `retry_count` for unreliable targets
4. **Validate Expressions**: Test parsing rules before deployment
5. **Document Workflows**: Add descriptions to complex steps

## Testing

Comprehensive test coverage includes:
- Individual rule validation
- Action configuration testing
- Complete step integration
- Serialization scenarios
- Mutual exclusion verification
- Pydantic version compatibility

Run tests with: `python test_scraper_steps.py`

## Troubleshooting

### Common Issues

1. **Validation Errors**: Check that all required fields are present
2. **Type Mismatches**: Ensure data types match model definitions
3. **Expression Syntax**: Verify parsing rule expressions are valid
4. **Circular References**: Avoid circular dependencies in nested structures

### Debugging Tips

```python
# Print detailed validation errors
try:
    step = ScraperStep(**invalid_data)
except ValidationError as e:
    print(e.json())

# Check model structure
print(ScraperStep.model_json_schema())
```

## Future Enhancements

Potential improvements:
- Support for async action configurations
- Additional parsing rule types (e.g., template-based extraction)
- Advanced retry strategies with exponential backoff
- Integration with scraping frameworks like Scrapy or BeautifulSoup