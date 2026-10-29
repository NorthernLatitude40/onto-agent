"""
Utility functions for applying parsing rules to API responses
"""
from typing import Any, Dict, List, Optional
import re
import json
import html
from lxml import etree


def apply_jsonpath_rule(data: Any, expression: str, target_field: str) -> Any:
    """
    Apply JSONPath expression to extract data from JSON response.
    
    Args:
        data: The JSON data (dict or list)
        expression: JSONPath expression string
        target_field: The field name to assign the extracted value to
        
    Returns:
        Extracted value(s) or None if not found
    """
    try:
        import jsonpath_ng as jp
        from jsonpath_ng import parse
        
        # Parse the JSONPath expression
        jsonpath_expr = parse(expression)
        
        # Search for matches in the data
        matches = [match.value for match in jsonpath_expr.find(data)]
        
        if not matches:
            return None
        elif len(matches) == 1:
            return matches[target_field] if isinstance(matches[0], dict) and target_field in matches[0] else matches[0]
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
        elif len(matches) == 1:
            # Single overall match - return it directly (could be full match or first group)
            return matches[0] if isinstance(matches[0], str) else matches[0][0]
        else:
            return matches
    except Exception as e:
        print(f"Regex parsing error: {e}")
        return None


def apply_parsing_rule(data: Any, rule: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Apply a single parsing rule to data and return the extracted field.
    """
    try:
        # 1. 在迴圈外面初始化字典（類似 Java 的 HashMap）
        vehicle_data = {}
        
        parser_type = rule.get("name")
        base_jsonpath = rule.get("jsonpath")
        css_selector = rule.get("css_selector")
        xpath_expr = rule.get("xpath")
        regex_pattern = rule.get("regex")
        mappings = rule.get("mappings")
        
        # 如果沒有 mappings，可能是一般的單一規則解析
        if not mappings:
            # 這裡可以保留你原本針對單一規則的處理邏輯
            pass

        # 2. 走訪 mappings 進行多欄位對應
        for m in mappings or []:
            source_key = m.get("source_key")
            target_field = m.get("target_field")
            
            if not target_field:
                continue
                
            parsed_value = None

            # 根據不同類型解析
            if parser_type == "jsonpath" and source_key:
                parsed_value = apply_jsonpath_rule(data, source_key, target_field)
            elif parser_type == "css_selector" and css_selector:
                parsed_value = apply_css_selector_rule(str(data), css_selector)
            elif parser_type == "xpath" and xpath_expr:
                parsed_value = apply_xpath_rule(str(data), xpath_expr)
            elif parser_type == "regex" and regex_pattern:
                parsed_value = apply_regex_rule(str(data), regex_pattern)
            else:
                continue

            # 型態轉換處理 (確保結果能安全轉成字串或保留結構)
            if parsed_value is not None and not isinstance(parsed_value, (str, int, float, bool, list)):
                try:
                    parsed_value = str(parsed_value)
                except Exception:
                    parsed_value = json.dumps(parsed_value)
            
            # 3. 像 Java 的 map.put() 一樣，塞進字典裏
            vehicle_data[target_field] = parsed_value
        
        # 4. 【重要】return 必須移到迴圈的「外面」，確保所有欄位都跑完才回傳！
        return vehicle_data
    
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
