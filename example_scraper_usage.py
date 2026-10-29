#!/usr/bin/env python3
"""
Example usage of the enhanced scraper step models.
This demonstrates a complete scraping workflow for vehicle data extraction.
"""

from src.model.scraper_step_models import (
    ScraperStep,
    ApiStepConfig,
    PlaywrightStepConfig,
    StaticHtmlStepConfig,
    JsonPathRule,
    CssSelectorRule,
    XpathRule,
    RegexRule
)

def create_vehicle_scraping_workflow():
    """
    Create a complete vehicle scraping workflow with multiple steps.
    This demonstrates the separation of concerns between step actions and parsing rules.
    """

    print("Creating vehicle scraping workflow...")

    # Step 1: API call to get vehicle listings (JSON response)
    api_rule = JsonPathRule(expression="$.vehicles[*].{name: name, price: price, url: details_url}")
    api_action = ApiStepConfig(
        url="https://api.example.com/vehicles",
        method="POST",
        params={"category": "campervans", "limit": 50},
        headers={"Authorization": "Bearer token123"},
        body={"filters": {"type": ["campervan", "motorhome"], "available": True}}
    )

    vehicle_listing_step = ScraperStep(
        step_name="Fetch vehicle listings",
        action_config=api_action,
        parsing_rules=api_rule,
        delay=500,
        retry_count=2,
        description="Get list of available campervans and motorhomes"
    )

    # Step 2: Playwright navigation to extract detailed data (HTML)
    playwright_rule = CssSelectorRule(expression=".vehicle-detail h1")
    playwright_action = PlaywrightStepConfig(
        url="https://example.com/vehicles/{vehicle_id}",
        wait_for_selector="#vehicle-details",
        click_selectors=["#specs-tab", "#features-tab"],
        scroll_to_bottom=True
    )

    vehicle_details_step = ScraperStep(
        step_name="Extract vehicle details",
        action_config=playwright_action,
        parsing_rules=playwright_rule,
        delay=1000,
        retry_count=3,
        description="Navigate to each vehicle page and extract detailed information"
    )

    # Step 3: Static HTML extraction for pricing data
    price_rule = RegexRule(
        expression=r"Price: \\$(\\d+,?\\d+)",
        flags="multiline"
    )
    html_action = StaticHtmlStepConfig(
        url="https://example.com/vehicles/pricing",
        encoding="utf-8"
    )

    pricing_step = ScraperStep(
        step_name="Extract pricing information",
        action_config=html_action,
        parsing_rules=price_rule,
        delay=200,
        description="Fetch and parse pricing data from static HTML page"
    )

    # Return the complete workflow
    workflow = [
        vehicle_listing_step,
        vehicle_details_step,
        pricing_step
    ]

    return workflow

def demonstrate_serialization():
    """Demonstrate how to serialize and deserialize the workflow"""
    print("\nDemonstrating serialization...")

    workflow = create_vehicle_scraping_workflow()

    # Convert entire workflow to JSON
    import json
    workflow_json = [step.model_dump() for step in workflow]
    json_str = json.dumps(workflow_json, indent=2)

    print("Serialized workflow:")
    print(json_str[:500] + "...")  # Print first part

    # Deserialize back to objects
    reconstructed_workflow = []
    for step_data in workflow_json:
        from src.model.scraper_step_models import ScraperStep
        step = ScraperStep(**step_data)
        reconstructed_workflow.append(step)

    print(f"\n✓ Successfully serialized and deserialized {len(workflow)} steps")

def demonstrate_rule_types():
    """Demonstrate different parsing rule types"""
    print("\nDemonstrating different parsing rule types...")

    # JSONPath for API responses
    json_rule = JsonPathRule(expression="$.results[*].vehicle.name")
    print(f"JSONPath: {json_rule.rule_type} -> {json_rule.expression}")

    # CSS Selector for HTML
    css_rule = CssSelectorRule(expression="div.vehicle-card h2.title")
    print(f"CSS Selector: {css_rule.rule_type} -> {css_rule.expression}")

    # XPath for XML/HTML
    xpath_rule = XpathRule(expression="//vehicle/details/price")
    print(f"XPath: {xpath_rule.rule_type} -> {xpath_rule.expression}")

    # Regex for text extraction
    regex_rule = RegexRule(
        expression=r"Total: (\\$\\d+\\.\\d{2})",
        flags="case_insensitive"
    )
    print(f"Regex: {regex_rule.rule_type} -> {regex_rule.expression}")
    if regex_rule.flags:
        print(f"  Flags: {regex_rule.flags}")

def demonstrate_action_types():
    """Demonstrate different action types"""
    print("\nDemonstrating different action types...")

    # API action
    api = ApiStepConfig(
        url="https://api.example.com/data",
        method="GET",
        params={"page": 1},
        headers={"Accept": "application/json"}
    )
    print(f"API: {api.action_type} -> {api.url}")

    # Playwright action
    playwright = PlaywrightStepConfig(
        url="https://example.com/page",
        wait_for_selector="#content"
    )
    print(f"Playwright: {playwright.action_type} -> {playwright.url}")

    # Static HTML action
    html = StaticHtmlStepConfig(url="https://example.com/static.html")
    print(f"Static HTML: {html.action_type} -> {html.url}")

def main():
    """Main demonstration function"""
    print("=" * 70)
    print("ENHANCED SCRAPER STEP MODELS - USAGE EXAMPLES")
    print("=" * 70)

    # Create and demonstrate a complete workflow
    workflow = create_vehicle_scraping_workflow()

    print(f"\nCreated workflow with {len(workflow)} steps:")
    for i, step in enumerate(workflow, 1):
        action_type = step.action_config.action_type
        rule_type = step.parsing_rules.rule_type if step.parsing_rules else "none"
        print(f"  {i}. {step.step_name} ({action_type}) -> {rule_type}")

    # Demonstrate different features
    demonstrate_serialization()
    demonstrate_rule_types()
    demonstrate_action_types()

    print("\n" + "=" * 70)
    print("✓ All examples completed successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()