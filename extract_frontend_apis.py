#!/usr/bin/env python3
"""Extract frontend API calls from TypeScript files."""
import re
from pathlib import Path

def extract_frontend_api_calls():
    """Extract all API calls from frontend TypeScript files."""
    api_calls = []
    frontend_dir = Path('../miniprogram-1/miniprogram')
    
    # Find all .ts files
    ts_files = list(frontend_dir.rglob('*.ts'))
    print(f"Found {len(ts_files)} TypeScript files")
    
    for ts_file in sorted(ts_files):
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all /api/v1/... URLs
        pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        matches = re.findall(pattern, content)
        
        if matches:
            print(f"  {ts_file.relative_to(frontend_dir)}: {len(matches)} API calls")
            for match in matches:
                api_calls.append(match)
    
    return sorted(set(api_calls))

if __name__ == '__main__':
    apis = extract_frontend_api_calls()
    print(f"\nTotal unique frontend API paths: {len(apis)}")
    for api in apis:
        print(f"  /api/v1/{api}")
