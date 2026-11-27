"""
Utility functions for applying parsing rules to API responses
"""
from typing import Any, Dict, List, Optional
import re
import json
import html
import traceback
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
            # Return the matched value directly, not indexed by target_field
            return matches[0]
        else:
            return matches
    except Exception as e:
        print(f"JSONPath parsing error (expression={expression!r}, field={target_field!r}): {e}")
        traceback.print_exc()
        return None


def apply_css_selector_rule(
    html_content: str,
    expression: str,
    attr: Optional[str] = None,
) -> Any:
    """
    Apply CSS selector to extract text or a specific attribute from HTML content.

    Args:
        html_content: HTML string content
        expression: CSS selector expression
        attr: Optional attribute name to extract (e.g. 'href', 'title').
              If None or 'text', extracts element text.

    Returns:
        Extracted value(s) or None if not found
    """
    try:
        tree = etree.HTML(html_content)
        if tree is None:
            return None

        elements = tree.cssselect(expression)
        if not elements:
            return None

        extract_attr = attr.strip() if isinstance(attr, str) and attr.strip() else None
        is_text = extract_attr is None or extract_attr.lower() in ("text", "inner_text")

        def _extract_one(el: Any) -> Any:
            if not is_text:
                val = el.get(extract_attr)
                if isinstance(val, str):
                    cleaned = html.unescape(val).strip()
                    return cleaned if cleaned else None
                return val

            text_val = "".join(el.itertext()) if hasattr(el, "itertext") else (el.text or "")
            cleaned = html.unescape(text_val).strip()
            return cleaned if cleaned else None

        # Always return a list for consistency with multi-item extraction
        return [_extract_one(el) for el in elements]
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


def apply_parsing_rule(data: Any, rules: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Apply a list of parsing rules to data and return the extracted fields combined into a single dictionary.
    """
    try:
        # 1. 在所有規則迴圈外面初始化字典，用來累積所有解析出來的欄位
        vehicle_data = {}
        
        # 2. 走訪 rules 數組中的每一個規則
        for rule in rules:
            parser_type = rule.get("parser_type") or rule.get("name")  # Fallback to name for backward compatibility
            # 規則只要帶有 JSONPath 特徵（jsonpath 欄位 / mappings 的 source_key 以 $ 開頭等），
            # 且沒有明確指定 css_selector/xpath/regex，就按 jsonpath 處理（name 可能是任意業務名稱）
            if is_jsonpath_rule(rule) and parser_type not in ("css_selector", "xpath", "regex"):
                parser_type = "jsonpath"
            base_jsonpath = rule.get("jsonpath")
            css_selector = rule.get("css_selector")
            xpath_expr = rule.get("xpath")
            regex_pattern = rule.get("regex")
            mappings = rule.get("mappings") or []
            
            # 如果沒有 mappings，可以根據需求看是否處理單一規則
            # 但是 css_selector 和 xpath 需要能夠在沒有 mappings 的情況下工作
            if not mappings and parser_type not in ["css_selector", "xpath"]:
                continue
            
            # 3. 走訪當前規則的 mappings 進行多欄位對應
            for m in mappings:
                source_key = m.get("source_key")
                target_field = m.get("target_field")
                attr = m.get("attr")
                
                if not target_field:
                    continue
                    
                parsed_value = None
                
                # 根據不同類型解析
                jsonpath_expr = source_key or m.get("selector")
                if parser_type == "jsonpath" and jsonpath_expr:
                    # If data is a list, apply JSONPath to each item
                    if isinstance(data, list) and len(data) > 0:
                        parsed_value = []
                        for item in data:
                            item_result = apply_jsonpath_rule(item, jsonpath_expr, target_field)
                            if item_result is not None:
                                parsed_value.append(item_result)
                        # Use first result or all results
                        if parsed_value:
                            parsed_value = parsed_value[0] if len(parsed_value) == 1 else parsed_value
                    else:
                        parsed_value = apply_jsonpath_rule(data, jsonpath_expr, target_field)
                elif parser_type == "css_selector":
                    if css_selector:
                        parsed_value = apply_css_selector_rule(str(data), css_selector, attr)
                    elif source_key:  # Support source_key as selector for backward compatibility
                        parsed_value = apply_css_selector_rule(str(data), source_key, attr)
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

                # 4. 塞進共用的字典裏
                vehicle_data[target_field] = parsed_value
            
            # Handle css_selector without mappings - extract elements directly
            if not mappings and parser_type == "css_selector" and css_selector:
                extracted_elements = apply_css_selector_rule(str(data), css_selector)
                if extracted_elements is not None:
                    vehicle_data["extracted_elements"] = extracted_elements
        
        # 5. 所有規則跑完後，一次回傳合併後的字典
        return vehicle_data
    
    except Exception as e: 
        print(f"Error applying parsing rules: {e}")
        traceback.print_exc()
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


def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _starts_with_dollar(value: Any) -> bool:
    """安全判斷值是否為以 $ 開頭的字串（None / 非字串一律視為 False）。"""
    return isinstance(value, str) and value.strip().startswith("$")


def is_jsonpath_rule(rule: Any) -> bool:
    """
    判斷單條解析規則是否為 JSONPath 規則。

    命中任一條件即視為 JSONPath：
    - 外層 name / parser_type 為 "jsonpath"
    - 外層存在非空的 jsonpath 欄位
    - 外層 selector / source_key 以 $ 開頭
    - mappings 中任一項的 source_key / selector 以 $ 開頭（None 值安全處理）
    """
    if rule is None:
        return False

    for key in ("parser_type", "name"):
        val = _get_attr_or_key(rule, key)
        if isinstance(val, str) and val.strip().lower() == "jsonpath":
            return True

    if _get_attr_or_key(rule, "jsonpath"):
        return True

    for key in ("selector", "source_key"):
        if _starts_with_dollar(_get_attr_or_key(rule, key)):
            return True

    mappings = _get_attr_or_key(rule, "mappings")
    if isinstance(mappings, list):
        for m in mappings:
            if m is None:
                continue
            for key in ("source_key", "selector"):
                if _starts_with_dollar(_get_attr_or_key(m, key)):
                    return True

    return False


def has_jsonpath_rules(rules: Optional[List[Any]]) -> bool:
    """規則列表中是否存在任一 JSONPath 規則。"""
    if not rules:
        return False
    return any(is_jsonpath_rule(r) for r in rules)


def expand_parsed_result(result: Any) -> List[Dict[str, Any]]:
    """
    把 apply_parsing_rules 的返回值規整為「記錄列表」。

    - list：原樣返回（過濾空項）
    - dict：若有字段值是 list（如 $.data[*].title 抽出多個值），按位置展開成多條記錄；
            非 list 的字段值廣播到每一條記錄
    - 全部字段都是 None / 空 dict：返回 []（避免把「什麼都沒匹配到」當成 1 條數據）
    """
    if result is None:
        return []

    if isinstance(result, list):
        return [r for r in result if r not in (None, {}, [])]

    if isinstance(result, dict):
        if not any(v is not None for v in result.values()):
            return []

        list_lengths = [len(v) for v in result.values() if isinstance(v, list)]
        num_records = max(list_lengths) if list_lengths else 0

        if num_records > 1:
            if len(set(list_lengths)) > 1:
                print(f"[!] JSONPath 各字段匹配條數不一致: {sorted(set(list_lengths))}，按位置對齊，缺失的位置該字段留空")
            expanded: List[Dict[str, Any]] = []
            for i in range(num_records):
                item: Dict[str, Any] = {}
                for key, value in result.items():
                    if isinstance(value, list):
                        if i < len(value):
                            item[key] = value[i]
                    else:
                        item[key] = value
                expanded.append(item)
            return expanded

        return [result]

    return [{"value": result}]


def parse_html_with_rules(
    html_content: str,
    rules: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Parse HTML content to extract multiple structured items using CSS selectors or XPath.
    Compatible with both (container, fields) and (css_selector/xpath, mappings with source_key/target_field).
    """
    try:
        print(f"[DEBUG] parse_html_with_rules file={__file__}, rules={rules}")
        tree = etree.HTML(html_content)
        if tree is None or not rules:
            print(f"[DEBUG] early return: tree_is_none={tree is None}, rules_empty={not rules}")
            return []

        items: List[Dict[str, Any]] = []

        for rule in rules:
            container_selector = (
                _get_attr_or_key(rule, "container")
                or _get_attr_or_key(rule, "css_selector")
                or _get_attr_or_key(rule, "xpath")
            )

            containers = []
            if isinstance(container_selector, str) and container_selector.strip():
                sel = container_selector.strip()
                try:
                    containers = tree.cssselect(sel)
                except Exception as css_err:
                    print(f"[DEBUG] selector error (cssselect {sel}): {css_err}")
                    try:
                        containers = tree.xpath(sel)
                    except Exception as xpath_err:
                        print(f"[DEBUG] selector error (xpath {sel}): {xpath_err}")
                        pass
            else:
                containers = [tree]

            print(f"[DEBUG] container_selector={container_selector!r}, containers_count={len(containers)}")
            if not containers:
                continue

            # 整理欄位設定：支援 dict (fields) 或 list (mappings)
            field_entries: List[tuple[str, Dict[str, Any]]] = []
            fields_config = _get_attr_or_key(rule, "fields")
            mappings_list = _get_attr_or_key(rule, "mappings")

            if isinstance(fields_config, dict) and fields_config:
                for fname, fcfg in fields_config.items():
                    if isinstance(fcfg, dict):
                        field_entries.append((str(fname), fcfg))
            elif isinstance(mappings_list, list) and mappings_list:
                for m in mappings_list:
                    fname = (
                        _get_attr_or_key(m, "target_field")
                        or _get_attr_or_key(m, "field")
                        or _get_attr_or_key(m, "name")
                    )
                    xpath_expr = _get_attr_or_key(m, "xpath")
                    css_expr = (
                        _get_attr_or_key(m, "selector")
                        or _get_attr_or_key(m, "css_selector")
                        or _get_attr_or_key(m, "source_key")
                    )
                    sel = xpath_expr if xpath_expr and not css_expr else css_expr
                    m_type = _get_attr_or_key(m, "type")
                    if not m_type:
                        m_type = "xpath" if (xpath_expr and not css_expr) else "css"

                    if fname and sel:
                        field_entries.append((
                            str(fname),
                            {
                                "selector": sel,
                                "attr": _get_attr_or_key(m, "attr"),
                                "type": str(m_type).lower(),
                            },
                        ))

            print(f"[DEBUG] field_entries_count={len(field_entries)}, field_entries={field_entries}")

            for container in containers:
                if not field_entries:
                    text_val = "".join(container.itertext()) if hasattr(container, "itertext") else str(container)
                    cleaned = html.unescape(text_val).strip()
                    if cleaned:
                        items.append({"text": cleaned})
                    continue

                item: Dict[str, Any] = {}
                for field_name, field_config in field_entries:
                    selector = field_config.get("selector")
                    attr = field_config.get("attr")
                    selector_type = (field_config.get("type") or "css").lower()
                    if not selector:
                        continue

                    if selector_type == "xpath":
                        try:
                            elements = container.xpath(selector)
                        except Exception as e:
                            print(f"[DEBUG] selector error (field={field_name}, xpath={selector}): {e}")
                            elements = []
                        if elements:
                            if len(elements) == 1:
                                el = elements[0]
                                if hasattr(el, "itertext"):
                                    val = "".join(el.itertext())
                                else:
                                    val = str(el)
                                cleaned = html.unescape(val).strip()
                                item[field_name] = cleaned if cleaned else None
                            else:
                                extracted_list = []
                                for el in elements:
                                    v = "".join(el.itertext()) if hasattr(el, "itertext") else str(el)
                                    c = html.unescape(v).strip()
                                    if c:
                                        extracted_list.append(c)
                                item[field_name] = extracted_list if extracted_list else None
                    else:
                        try:
                            elements = container.cssselect(selector)
                        except Exception as e:
                            print(f"[DEBUG] selector error (field={field_name}, css={selector}): {e}")
                            elements = []
                        if elements:
                            extract_attr = attr.strip() if isinstance(attr, str) and attr.strip() else None
                            is_text = extract_attr is None or extract_attr.lower() in ("text", "inner_text")

                            def _extract_one(el: Any) -> Any:
                                if not is_text:
                                    val = el.get(extract_attr)
                                    if isinstance(val, str):
                                        cleaned = html.unescape(val).strip()
                                        return cleaned if cleaned else None
                                    return val
                                text_val = "".join(el.itertext()) if hasattr(el, "itertext") else (el.text or "")
                                cleaned = html.unescape(text_val).strip()
                                return cleaned if cleaned else None

                            if len(elements) == 1:
                                item[field_name] = _extract_one(elements[0])
                            else:
                                item[field_name] = [_extract_one(el) for el in elements]

                if any(v is not None for v in item.values()):
                    items.append(item)

        return items
    except Exception as e:
        print(f"Error parsing HTML with rules: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_json_with_rules(data: Any, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    使用 JSONPath 和其他规则解析 JSON 数据。
    
    Args:
        data: API 响应数据（可以是单个 dict 或列表）
        rules: 解析规则列表
        
    Returns:
        解析后的数据字典
        
    Notes:
        - 处理单个 dict 和列表响应
        - 对于列表，对每个项应用规则并返回所有结果
        - 使用 apply_parsing_rule 进行实际 JSONPath 解析
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not rules:
        return {}
    
    # 确保数据是列表（即使单个 dict，也包装成列表以便统一处理）
    items_to_parse = data if isinstance(data, list) else [data]
    
    parsed_items = []
    item_count = len(items_to_parse)
    
    logger.info(f"[JSON 解析] 开始解析 {item_count} 个项目使用 JSONPath 规则")
    
    for idx, item in enumerate(items_to_parse):
        try:
            # 对每个项应用所有规则
            parsed_item = apply_parsing_rules(item, rules)
            if parsed_item:
                parsed_items.append(parsed_item)
        except Exception as e:
            logger.error(f"[JSON 解析] 解析项目 {idx+1}/{item_count} 失败: {e}", exc_info=True)
    
    result = {
        'items': parsed_items,
        'count': len(parsed_items),
        'success': True
    }
    
    logger.info(f"[JSON 解析] 完成。成功解析 {result['count']}/{item_count} 个项目")
    return result