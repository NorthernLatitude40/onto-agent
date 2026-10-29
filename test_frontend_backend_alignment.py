"""
Test to verify alignment between frontend parsing_rules and backend Pydantic models
"""

import json
from src.model.scraper_schema import ParsingRule, ScraperStep

# =============================================================================
# FRONTEND DATA STRUCTURE (as described in the issue)
# =============================================================================

frontend_parsing_rule = {
    "css_selector": None,
    "id": None,
    "jsonpath": "$.vehicle.name",
    "mappings": [
        {"source_key": "0.vehicle.name", "target_field": "name"},
        {"source_key": "0.pricing.total", "target_field": "total_price"},
        {"source_key": "0.pricing.averageRating", "target_field": "rating"}
    ],
    "name": "jsonpath"
}

# =============================================================================
# TEST 1: Validate ParsingRule model accepts frontend structure
# =============================================================================

def test_parsing_rule_model():
    """Test that the backend ParsingRule model accepts frontend data structure"""
    print("Testing ParsingRule model with frontend data...")

    try:
        # Create instance using frontend data
        rule = ParsingRule(**frontend_parsing_rule)
        print(f"✓ ParsingRule created successfully")
        print(f"  - name: {rule.name}")
        print(f"  - jsonpath: {rule.jsonpath}")
        print(f"  - css_selector: {rule.css_selector}")
        print(f"  - id: {rule.id}")

        # Check if mappings field exists
        if hasattr(rule, 'mappings'):
            print(f"  - mappings count: {len(rule.mappings) if rule.mappings else 0}")
            return True
        else:
            print("✗ mappings field not found in ParsingRule model!")
            return False

    except Exception as e:
        print(f"✗ Error creating ParsingRule: {e}")
        return False

# =============================================================================
# TEST 2: Validate ScraperStep model with parsing_rules containing mappings
# =============================================================================

def test_scraper_step_model():
    """Test that the backend ScraperStep model accepts frontend data structure"""
    print("\nTesting ScraperStep model with frontend data...")

    try:
        # Create a complete step with frontend data
        step_data = {
            "id": "step-1",
            "name": "Extract vehicle info",
            "mode": "api",
            "target_url": "https://example.com/api/vehicles",
            "method": "GET",
            "params": {"page": 1},
            "headers": {"Accept": "application/json"},
            "parsing_rules": frontend_parsing_rule,
            "delay": 1000,
            "retry_count": 3
        }

        step = ScraperStep(**step_data)
        print(f"✓ ScraperStep created successfully")
        print(f"  - name: {step.name}")
        print(f"  - mode: {step.mode}")

        # Check parsing rules
        if step.parsing_rules:
            print(f"  - parsing_rules.name: {step.parsing_rules.name}")
            print(f"  - parsing_rules.jsonpath: {step.parsing_rules.jsonpath}")

            # Check if mappings are preserved
            if hasattr(step.parsing_rules, 'mappings'):
                print(f"  - parsing_rules.mappings count: {len(step.parsing_rules.mappings) if step.parsing_rules.mappings else 0}")
                return True
            else:
                print("✗ mappings field not found in step.parsing_rules!")
                return False
        else:
            print("✗ parsing_rules not preserved!")
            return False

    except Exception as e:
        print(f"✗ Error creating ScraperStep: {e}")
        return False

# =============================================================================
# TEST 3: Validate JSON serialization preserves mappings
# =============================================================================

def test_json_serialization():
    """Test that JSON serialization preserves the mappings field"""
    print("\nTesting JSON serialization...")

    try:
        # Create ParsingRule with frontend data
        rule = ParsingRule(**frontend_parsing_rule)

        # Serialize to JSON (like the API does)
        json_str = json.dumps(rule.model_dump())
        print(f"✓ Serialized to JSON: {json_str}")

        # Deserialize back
        deserialized = json.loads(json_str)
        print(f"✓ Deserialized from JSON")

        # Check if mappings are preserved in the JSON
        if 'mappings' in deserialized:
            print(f"  - mappings preserved in JSON: {len(deserialized['mappings'])} items")
            return True
        else:
            print("✗ mappings field not found in serialized JSON!")
            return False

    except Exception as e:
        print(f"✗ Error during serialization test: {e}")
        return False

# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FRONTEND/BACKEND ALIGNMENT TEST")
    print("=" * 60)

    results = []
    results.append(test_parsing_rule_model())
    results.append(test_scraper_step_model())
    results.append(test_json_serialization())

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"Tests passed: {sum(results)}/{len(results)}")

    if all(results):
        print("✓ All tests passed - frontend/backend alignment is correct")
    else:
        print("✗ Some tests failed - there are alignment issues!")
        print("\nThe issue appears to be that the backend ParsingRule model")
        print("does not include a 'mappings' field, which is sent by the frontend.")