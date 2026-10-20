"""
Utility functions for applying parsing rules to API responses
"""
from typing import Any, Dict, List, Optional
import re
import json
import html
from lxml import etree


def apply_jsonpath_rule(data: Any, expression: str) -> Any:
    """
    Apply JSONPath expression to extract data from JSON response.
    
    Args:
        data: The JSON data (dict or list)
        expression: JSONPath expression string
        
    Returns:
        Extracted value(s) or None if not found
    """
    try:
        import jsonpath_ng as jp
        from jsonpath_ng.ext import parse
        
        # Parse the JSONPath expression
        jsonpath_expr = parse(expression)
        
        # Search for matches in the data
        matches = [match.value for match in jsonpath_expr.find(data)]
        
        if not matches:
            return None
        elif len(matches) == 1:
            return matches[0]
        else:
            return matches
    except Exception as e:
        print(f"JSONPath parsing error: {e}")
        return None


def apply_css_selector_rule(html_content: str, expression: str) -> Any:
    """
    Apply CSS selector to extract data from HTML content.
    
    Args:
        html_content: HTML string content
        expression: CSS selector expression
        
    Returns:
        Extracted element(s) or None if not found
    """
    try:
        # Parse HTML content
        tree = etree.HTML(html_content)
        
        # Apply CSS selector using lxml's built-in method
        elements = tree.cssselect(expression)
        
        if not elements:
            return None
        elif len(elements) == 1:
            # Return text content of single element
            text = elements[0].text if elements[0].text is not None else ""
            return html.unescape(text.strip())
        else:
            # Return list of text contents for multiple elements
            return [
                html.unescape(text.strip())
                if (text := el.text) is not None
                else ""
                for el in elements
            ]
    except Exception as e:
        print(f"CSS selector parsing error: {e}")
        return None


def apply_xpath_rule(html_content: str, expression: str) -> Any:
    """
    Apply XPath expression to extract data from HTML content.
    
    Args:
        html_content: HTML string content
        expression: XPath expression string
        
    Returns:
        Extracted value(s) or None if not found
    """
    try:
        # Parse HTML content
        tree = etree.HTML(html_content)
        
        # Apply XPath expression
        elements = tree.xpath(expression)
        
        if not elements:
            return None
        elif len(elements) == 1:
            # Return text content of single element
            return html.unescape(str(elements[0]).strip())
        else:
            # Return list of string representations for multiple elements
            return [html.unescape(str(el).strip()) for el in elements]
    except Exception as e:
        print(f"XPath parsing error: {e}")
        return None


def apply_regex_rule(text: str, pattern: str) -> Any:
    """
    Apply regex pattern to extract data from text.
    
    Args:
        text: Text content to search
        pattern: Regex pattern string
        
    Returns:
        Extracted match(es) or None if not found
    """
    try:
        # Compile regex pattern
        regex = re.compile(pattern)
        
        # Search for matches
        matches = regex.findall(text)
        
        if not matches:
            return None
        elif len(matches) == 1 and len(matches[0]) == 1:
            # Single group match - return the value directly
            return matches[0][0]
        else:
            return matches
    except Exception as e:
        print(f"Regex parsing error: {e}")
        return None


def apply_parsing_rule(data: Any, rule: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Apply a single parsing rule to data and return the extracted field.
    
    Args:
        data: The input data (can be dict for JSONPath, or string for HTML/XML/Regex)
        rule: Parsing rule dictionary with parser_type, expression, output_field
        
    Returns:
        Dictionary with {output_field: extracted_value} or None if parsing fails
    """
    try:
        result = None
        
        parser_type = rule.get("name"),
        expression = rule.get("jsonpath"),
        output_field = rule.get("output_field"),
        # Determine which parser to use based on the rule type
        # parser_type = rule.get("parser_type")
        # expression = rule.get("expression", "")
        # output_field = rule.get("output_field", "result_data")
        
        if not expression:
            return None
        
        # Apply the appropriate parser based on type
        if parser_type[0] == "jsonpath":
            result = apply_jsonpath_rule(data, expression[0])
        elif parser_type == "css_selector":
            result = apply_css_selector_rule(str(data), expression[0])
        elif parser_type == "xpath":
            result = apply_xpath_rule(str(data), expression[0])
        elif parser_type == "regex":
            result = apply_regex_rule(str(data), expression[0])
        else:
            print(f"Unknown parser type: {parser_type}")
            return None
        
        # Convert result to string if it's not already
        if result is not None and not isinstance(result, (str, int, float, bool)):
            try:
                result = str(result)
            except Exception:
                result = json.dumps(result)
        
        # Return type is Dict[str, str] to match the signature
        return {str(output_field): str(result)} if result is not None else None
    
    except Exception as e:
        print(f"Error applying parsing rule: {e}")
        return None


def apply_parsing_rules(data: Any, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply multiple parsing rules to data and return combined results.
    
    Args:
        data: The input data (can be dict for JSONPath, or string for HTML/XML/Regex)
        rules: List of parsing rule dictionaries
        
    Returns:
        Dictionary with all extracted fields from successful rules
    """
    results = {}
    
    if not rules:
        return results
    
    result = apply_parsing_rule(data, rules)
    # for rule in rules:
    #     try:
    #         result = apply_parsing_rule(data, rule)
    #         if result:
    #             results.update(result)
    #     except Exception as e:
    #         print(f"Error applying rule {rule.get('name', 'unnamed')}: {e}")
    #         continue
    if result:
        results.update(result)

    return results
