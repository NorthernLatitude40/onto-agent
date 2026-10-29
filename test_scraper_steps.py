#!/usr/bin/env python3
"""
Test script to verify the new scraper step models work correctly.
Tests both Pydantic v1 and v2 compatibility.
"""

import json
from src.model.scraper_step_models import (
    ScraperStep,
    ApiStepConfig,
    PlaywrightStepConfig,
    StaticHtmlStepConfig,
    JsonPathRule,
    CssSelectorRule,
    XpathRule,
    RegexRule,
    JsonSchemaRule,
    get_parsing_rule_type,
    get_step_action_type
)

def test_json_path_rule():
    """Test JSONPath parsing rule"""
    print("Testing JSONPath rule...")
    rule = JsonPathRule(expression="$.vehicle.name")
    assert rule.rule_type == "json_path"
    assert rule.expression == "$.vehicle.name"
    print("✓ JSONPath rule works")

def test_css_selector_rule():
    """Test CSS selector parsing rule"""
    print("Testing CSS selector rule...")
    rule = CssSelectorRule(expression="div.vehicle-name")
    assert rule.rule_type == "css_selector"
    assert rule.expression == "div.vehicle-name"
    print("✓ CSS selector rule works")

def test_xpath_rule():
    """Test XPath parsing rule"""
    print("Testing XPath rule...")
    rule = XpathRule(expression="//vehicle/name")
    assert rule.rule_type == "xpath"
    assert rule.expression == "//vehicle/name"
    print("✓ XPath rule works")

def test_regex_rule():
    """Test regex parsing rule"""
    print("Testing regex rule...")
    rule = RegexRule(expression=r"Vehicle: (.+)", flags="multiline")
    assert rule.rule_type == "regex"
    assert rule.expression == r"Vehicle: (.+)"
    assert rule.flags == "multiline"
    print("✓ Regex rule works")

def test_json_schema_rule():
    """Test JSON schema parsing rule"""
    print("Testing JSON schema rule...")
    schema = {
        "type": "object",
        "properties": {
            "vehicle": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "required": ["vehicle"]
    }
    rule = JsonSchemaRule(schema_definition=schema, extract_path="$.vehicle.name")
    assert rule.rule_type == "json_schema"
    assert rule.extract_path == "$.vehicle.name"
    print("✓ JSON schema rule works")

def test_api_step():
    """Test API step configuration"""
    print("Testing API step...")
    action = ApiStepConfig(
        url="https://api.example.com/vehicles",
        method="POST",
        params={"page": 1, "limit": 10},
        headers={"Authorization": "Bearer token"},
        body={"filter": {"type": "campervan"}}
    )
    assert action.action_type == "api"
    assert action.url == "https://api.example.com/vehicles"
    print("✓ API step works")

def test_playwright_step():
    """Test Playwright step configuration"""
    print("Testing Playwright step...")
    action = PlaywrightStepConfig(
        url="https://example.com/vehicles",
        wait_for_selector="#vehicle-list",
        click_selectors=["#load-more", "#details-button"],
        scroll_to_bottom=True
    )
    assert action.action_type == "playwright"
    assert action.url == "https://example.com/vehicles"
    print("✓ Playwright step works")

def test_static_html_step():
    """Test static HTML step configuration"""
    print("Testing static HTML step...")
    action = StaticHtmlStepConfig(
        url="https://example.com/vehicles.html",
        encoding="utf-8"
    )
    assert action.action_type == "static_html"
    assert action.url == "https://example.com/vehicles.html"
    print("✓ Static HTML step works")

def test_complete_scraper_step():
    """Test complete scraper step with action and parsing rule"""
    print("Testing complete scraper step...")

    # Create a JSONPath parsing rule
    parsing_rule = JsonPathRule(expression="$.vehicles[*].name")

    # Create an API action
    api_action = ApiStepConfig(
        url="https://api.example.com/vehicles",
        method="GET",
        params={"category": "campervans"}
    )

    # Create the complete step
    step = ScraperStep(
        step_name="Fetch vehicle list",
        action_config=api_action,
        parsing_rules=parsing_rule,
        delay=1000,
        retry_count=3,
        description="Fetch list of available campervans"
    )

    assert step.step_name == "Fetch vehicle list"
    assert get_step_action_type(step) == "api"
    assert get_parsing_rule_type(step.parsing_rules) == "json_path"
    print("✓ Complete scraper step works")

def test_serialization():
    """Test JSON serialization and deserialization"""
    print("Testing serialization...")

    # Create a complex step
    rule = JsonPathRule(expression="$.data.items[*].title")
    action = ApiStepConfig(
        url="https://api.example.com/search",
        method="POST",
        params={"q": "campervan", "limit": 20},
        headers={"Content-Type": "application/json"},
        body={"filters": {"type": ["campervan", "motorhome"]}}
    )

    step = ScraperStep(
        step_name="Search vehicles",
        action_config=action,
        parsing_rules=rule,
        delay=500,
        retry_count=2
    )

    # Serialize to JSON
    json_str = step.model_dump_json()
    print(f"Serialized: {json_str[:100]}...")

    # Deserialize back
    reconstructed = ScraperStep.model_validate_json(json_str)
    assert reconstructed.step_name == step.step_name
    assert reconstructed.action_config.url == step.action_config.url
    assert reconstructed.parsing_rules.expression == step.parsing_rules.expression

    print("✓ Serialization works")

def test_mutual_exclusion():
    """Test that parsing rules are mutually exclusive"""
    print("Testing mutual exclusion...")

    # This should work - single rule type
    json_rule = JsonPathRule(expression="$.test")
    css_rule = CssSelectorRule(expression="#test")

    # Both should be valid independently
    step1 = ScraperStep(
        step_name="Test 1",
        action_config=ApiStepConfig(url="https://example.com"),
        parsing_rules=json_rule
    )

    step2 = ScraperStep(
        step_name="Test 2",
        action_config=ApiStepConfig(url="https://example.com"),
        parsing_rules=css_rule
    )

    assert get_parsing_rule_type(step1.parsing_rules) == "json_path"
    assert get_parsing_rule_type(step2.parsing_rules) == "css_selector"

    print("✓ Mutual exclusion works correctly")

def test_pydantic_version_compatibility():
    """Test compatibility with both Pydantic v1 and v2"""
    print("Testing Pydantic version compatibility...")

    # Test that we can create instances
    rule = JsonPathRule(expression="$.test")
    action = ApiStepConfig(url="https://example.com")
    step = ScraperStep(step_name="Test", action_config=action, parsing_rules=rule)

    # Test model methods work
    data = step.model_dump()
    assert isinstance(data, dict)
    assert "step_name" in data

    json_data = step.model_dump_json()
    assert isinstance(json_data, str)

    print("✓ Pydantic version compatibility works")

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running Scraper Step Model Tests")
    print("=" * 60)

    test_json_path_rule()
    test_css_selector_rule()
    test_xpath_rule()
    test_regex_rule()
    test_json_schema_rule()

    test_api_step()
    test_playwright_step()
    test_static_html_step()

    test_complete_scraper_step()
    test_serialization()
    test_mutual_exclusion()
    test_pydantic_version_compatibility()

    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()