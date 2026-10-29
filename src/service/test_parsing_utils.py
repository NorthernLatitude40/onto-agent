#!/usr/bin/env python3
"""
Test suite for parsing_utils module.
Tests the apply_parsing_rule function with various parser types and edge cases.
"""

import json
from parsing_utils import apply_parsing_rule

def test_jsonpath_parsing():
    """Test JSONPath parsing functionality."""
    data = {'vehicle': {'name': 'Toyota', 'model': 'Camry'}}
    rule = {
        'name': 'jsonpath',
        'jsonpath': '$..name',
        'output_field': 'car_name'
    }
    result = apply_parsing_rule(data, rule)
    # JSONPath returns single value when only one match
    expected_result = {'car_name': 'Toyota'}
    assert result == expected_result, f"Expected {expected_result}, got {result}"
    print("✓ JSONPath parsing test passed")

def test_css_selector_with_dict():
    """Test CSS selector with dict data (should return None gracefully)."""
    data = {'div': {'content': 'Hello World'}}
    rule = {
        'name': 'css_selector',
        'css_selector': 'div.content',
        'output_field': 'content'
    }
    result = apply_parsing_rule(data, rule)
    assert result is None, f"Expected None for CSS selector with dict data, got {result}"
    print("✓ CSS selector with dict test passed")

def test_xpath_with_dict():
    """Test XPath with dict data (should return None gracefully)."""
    data = {'root': {'child': 'value'}}
    rule = {
        'name': 'xpath',
        'xpath': '/root/child',
        'output_field': 'result'
    }
    result = apply_parsing_rule(data, rule)
    assert result is None, f"Expected None for XPath with dict data, got {result}"
    print("✓ XPath with dict test passed")

def test_regex_with_dict():
    """Test regex pattern with dict data (should work on string representation)."""
    data = {'text': 'Hello World'}
    rule = {
        'name': 'regex',
        'regex': r'Hello (\w+)',
        'output_field': 'match'
    }
    result = apply_parsing_rule(data, rule)
    expected_result = {'match': 'World'}
    assert result == expected_result, f"Expected {expected_result} for regex with dict data, got {result}"
    print("✓ Regex with dict test passed")

def test_unknown_parser_type():
    """Test unknown parser type (should return None gracefully)."""
    data = {'vehicle': {'name': 'Toyota'}}
    rule = {
        'name': 'unknown_parser',
        'jsonpath': '$..name',
        'output_field': 'result'
    }
    result = apply_parsing_rule(data, rule)
    assert result is None, f"Expected None for unknown parser type, got {result}"
    print("✓ Unknown parser type test passed")

def test_missing_expression():
    """Test missing expression field (should return None gracefully)."""
    data = {'vehicle': {'name': 'Toyota'}}
    rule = {
        'name': 'jsonpath',
        'output_field': 'result'
    }
    result = apply_parsing_rule(data, rule)
    assert result is None, f"Expected None for missing expression, got {result}"
    print("✓ Missing expression test passed")

def test_empty_data():
    """Test with empty data."""
    data = {}
    rule = {
        'name': 'jsonpath',
        'jsonpath': '$..name',
        'output_field': 'result'
    }
    result = apply_parsing_rule(data, rule)
    assert result is None, f"Expected None for empty data, got {result}"
    print("✓ Empty data test passed")

def test_complex_jsonpath():
    """Test complex JSONPath expression."""
    data = {
        'products': [
            {'name': 'Laptop', 'price': 1000},
            {'name': 'Phone', 'price': 800}
        ]
    }
    rule = {
        'name': 'jsonpath',
        'jsonpath': '$..name',
        'output_field': 'product_names'
    }
    result = apply_parsing_rule(data, rule)
    assert result == {'product_names': ['Laptop', 'Phone']}, f"Expected {{'product_names': ['Laptop', 'Phone']}}, got {result}"
    print("✓ Complex JSONPath test passed")

def run_all_tests():
    """Run all tests."""
    print("Running parsing_utils tests...\n")
    try:
        test_jsonpath_parsing()
        test_css_selector_with_dict()
        test_xpath_with_dict()
        test_regex_with_dict()
        test_unknown_parser_type()
        test_missing_expression()
        test_empty_data()
        test_complex_jsonpath()
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False

    return True

if __name__ == '__main__':
    run_all_tests()