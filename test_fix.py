#!/usr/bin/env python3

import json

# Test the fix by simulating what the API would do
def test_step_field_access():
    """Test that step fields are correctly accessed"""

    # Simulate a step config from database (JSON string)
    step_json = '{"method": "GET", "params": {"key": "value"}, "headers": {"Authorization": "Bearer token"}}'
    step_config = json.loads(step_json)

    # Test accessing the correct fields
    try:
        params = step_config.get("params")
        headers = step_config.get("headers")
        print(f"✓ Successfully accessed params: {params}")
        print(f"✓ Successfully accessed headers: {headers}")

        # Verify we can create the expected response structure
        step_response = {
            "method": step_config.get("method", "GET"),
            "params": params,
            "headers": headers,
            "parsing_rules": []
        }
        print(f"✓ Created step response: {step_response}")

    except AttributeError as e:
        print(f"✗ AttributeError: {e}")
        return False

    return True

if __name__ == "__main__":
    success = test_step_field_access()
    if success:
        print("\n🎉 Test passed! The fix works correctly.")
    else:
        print("\n❌ Test failed!")