#!/usr/bin/env python3
"""
Debug frontend API extraction.
"""
import re
from pathlib import Path

def extract_frontend_api_calls_debug():
    """Extract all API calls from frontend TypeScript files with debug output."""
    api_calls = []
    
    # Find all .ts files in the miniprogram directory
    ts_files = list(Path('../miniprogram-1/miniprogram').rglob('*.ts'))
    print(f"Found {len(ts_files)} TS files")
    
    for ts_file in sorted(ts_files)[:5]:  # Check first 5 files
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"\n=== {ts_file} ===")
        
        # Find all /api/v1/... URLs
        pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        matches = re.findall(pattern, content)
        print(f"Simple URL matches: {len(matches)}")
        for match in matches[:3]:
            print(f"  - {match}")
        
        # Also look for method + url patterns
        method_pattern = r"method:\s*['\"](GET|POST|PUT|DELETE|PATCH)['\"].*?url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        method_matches = re.findall(method_pattern, content, re.DOTALL)
        print(f"Method+URL matches: {len(method_matches)}")
        for match in method_matches[:3]:
            print(f"  - {match[0]} {match[1]}")
        
        # Look for inline format like url: '/api/v1/...', method: 'POST'
        inline_pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        inline_matches = re.findall(inline_pattern, content)
        print(f"Inline matches: {len(inline_matches)}")
        for match in inline_matches[:3]:
            print(f"  - {match}")
        
        # Process matches with methods
        for method, path in method_matches:
            clean_path = path.strip()
            api_calls.append((method, clean_path))
        
        # Process remaining matches without explicit method (default to GET)
        seen_paths = set(p for m, p in method_matches)
        for path in matches:
            if path not in seen_paths:
                clean_path = path.strip()
                api_calls.append(('GET', clean_path))
    
    print(f"\n=== TOTAL API CALLS FOUND: {len(api_calls)} ===")
    for method, path in sorted(api_calls)[:10]:
        print(f"{method} /api/v1/{path}")
    
    return api_calls

if __name__ == '__main__':
    extract_frontend_api_calls_debug()