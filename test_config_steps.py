"""Test script to verify config_routes.py handles steps correctly"""
from src.model.scraper_schema import ScraperStep, ParsingRule

# Test data that mimics what get_steps_by_config_id returns
raw_step_data = [
    {
        "id": "step-1",
        "scraper_config_id": 1,
        "name": "获取车型列表",
        "target_type": "api",
        "target_url": "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2",
        "config": {
            "method": "POST",
            "params": '{"pickupdate": "2026-11-10"}',
            "headers": '{"Content-Type": "application/json"}',
            "parsing_rules": [
                {
                    "id": "rule-1",
                    "name": "解析车型列表",
                    "jsonpath": "$.cars[*].vehiclecategory",
                    "output_field": "model_name",
                    "required": True
                }
            ],
            "delay": 1000,
            "retry_count": 3
        },
        "enabled": True
    }
]

# Test the conversion logic from config_routes.py
steps = []
for step in raw_step_data:
    # Convert target_type back to mode field
    step_dict = {
        "id": step["id"],
        "name": step["name"],
        "mode": step.get("target_type", "api"),  # Map target_type to mode
        "target_url": step["target_url"],
    }
    # Merge config data into step_dict
    if step.get("config"):
        config_data = step["config"]
        for key in ["method", "params_json", "headers_json", "delay", "retry_count"]:
            if key in config_data:
                # Map params to params_json, headers to headers_json
                mapped_key = key
                if key == "params":
                    mapped_key = "params_json"
                elif key == "headers":
                    mapped_key = "headers_json"
                step_dict[mapped_key] = config_data[key]
    
    # Create ScraperStep instance
    steps.append(ScraperStep(**step_dict))

print(f"Successfully converted {len(steps)} raw steps to ScraperStep objects")
print(f"First step type: {type(steps[0])}")
print(f"First step mode: {steps[0].mode}")
print(f"First step has parsing_rules: {hasattr(steps[0], 'parsing_rules')}")

# Verify the structure matches what's expected
assert len(steps) == 1, "Should have 1 step"
assert isinstance(steps[0], ScraperStep), "Step should be a ScraperStep instance"
assert steps[0].mode == "api", "Mode should be 'api'"
assert steps[0].name == "获取车型列表", "Name should match"
print("\n✓ All assertions passed!")
