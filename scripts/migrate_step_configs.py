"""
Migration script to convert legacy step configurations to dual-mode format.

This script handles the transformation from the old format where steps had a
'mode' field and separate fields for different modes, to the new unified format
where each step has an action_config that contains mode-specific configuration.
"""
import json
from typing import Dict, Any, List

def migrate_legacy_step_to_new_format(legacy_step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a legacy step format to the new dual-mode format.
    
    Legacy format had separate fields like url, method, params, etc.
    New format uses action_config with mode-specific configuration.
    
    Args:
        legacy_step: Dictionary containing legacy step data
        
    Returns:
        Dictionary in the new dual-mode format
    """
    # Extract common fields
    step_name = legacy_step.get('name', '')
    parsing_rules = legacy_step.get('parsing_rules')
    delay = legacy_step.get('delay')
    retry_count = legacy_step.get('retry_count')
    
    # Determine mode and create appropriate action_config
    mode = legacy_step.get('mode', 'api')
    target_url = legacy_step.get('target_url', '')
    method = legacy_step.get('method', 'GET')
    params = legacy_step.get('params')
    headers = legacy_step.get('headers')
    
    action_config = {}
    
    if mode == 'api':
        # API mode configuration
        action_config = {
            "action_type": "api",
            "url": target_url,
            "method": method,
            "params": params or {},
            "headers": headers or {}
        }
    elif mode == 'playwright' or mode == 'browser':
        # Browser/Playwright mode configuration
        action_config = {
            "action_type": "playwright",
            "url": target_url,
            "wait_for_selector": None,  # Can be set from legacy config if available
            "click_selectors": [],      # Can be derived from legacy config
            "scroll_to_bottom": False
        }
    elif mode == 'html' or mode == 'static_html':
        # Static HTML mode configuration
        action_config = {
            "action_type": "static_html",
            "html_content": legacy_step.get('html', '')
        }
    else:
        # Default to API mode if unknown
        action_config = {
            "action_type": "api",
            "url": target_url,
            "method": method or 'GET'
        }
    
    # Build the new step structure
    new_step = {
        "name": step_name,
        "parsing_rules": parsing_rules,
        "delay": delay,
        "retry_count": retry_count,
        "action_config": action_config
    }
    
    return new_step

def migrate_legacy_steps_to_new_format(legacy_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert a list of legacy steps to the new dual-mode format.
    
    Args:
        legacy_steps: List of dictionaries containing legacy step data
        
    Returns:
        List of dictionaries in the new dual-mode format
    """
    return [migrate_legacy_step_to_new_format(step) for step in legacy_steps]

def migrate_scraper_config(legacy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate an entire scraper configuration from legacy to new format.
    
    Args:
        legacy_config: Dictionary containing the legacy scraper config
        
    Returns:
        Dictionary in the new dual-mode format
    """
    # Extract top-level fields
    config_name = legacy_config.get('name', '')
    description = legacy_config.get('description', '')
    schedule = legacy_config.get('schedule')
    is_active = legacy_config.get('is_active', True)
    
    # Migrate steps
    legacy_steps = legacy_config.get('steps', [])
    new_steps = migrate_legacy_steps_to_new_format(legacy_steps)
    
    # Build the new config structure
    new_config = {
        "name": config_name,
        "description": description,
        "schedule": schedule,
        "is_active": is_active,
        "steps": new_steps
    }
    
    return new_config

def main():
    """
    Main function to run the migration.
    
    This reads legacy configurations from a file, migrates them,
    and writes the new format to another file.
    """
    import sys
    import os
    
    if len(sys.argv) != 3:
        print("Usage: python migrate_step_configs.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Read legacy configurations
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        sys.exit(1)
    
    with open(input_file, 'r') as f:
        legacy_configs = json.load(f)
    
    # Migrate each configuration
    new_configs = []
    for config in legacy_configs:
        try:
            new_config = migrate_scraper_config(config)
            new_configs.append(new_config)
        except Exception as e:
            print(f"Error migrating config {config.get('name', 'unknown')}: {e}")
            continue
    
    # Write migrated configurations
    with open(output_file, 'w') as f:
        json.dump(new_configs, f, indent=2)
    
    print(f"Successfully migrated {len(new_configs)} configurations to {output_file}")

if __name__ == "__main__":
    main()
