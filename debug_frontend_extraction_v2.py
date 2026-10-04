#!/usr/bin/env python3
"""
Debug script to extract API calls from frontend TypeScript files.
This version uses a more flexible regex pattern.
"""
import os
import re
from pathlib import Path

def find_ts_files(directory):
    """Find all .ts files in the directory recursively."""
    ts_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.ts'):
                ts_files.append(os.path.join(root, file))
    return ts_files

def extract_api_calls_v2(file_path):
    """
    Extract API calls using a more flexible pattern.
    Looks for request({ url: '/api/v1/...', method: '...' })
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    # Pattern 1: request({ url: '/api/v1/...', method: '...' })
    pattern1 = r"request\s*\(\s*\{[^}]*url\s*:\s*['\"]/api/v1/[^'\"]+['\"][^}]*method\s*:\s*['\"]([A-Z]+)['\"][^}]*\}\s*\)"
    
    # Pattern 2: request({ url: '/api/v1/...', method: '...' })
    pattern2 = r"request\s*\(\s*\{[^}]*url\s*:\s*['\"]/api/v1/[^'\"]+['\"][^}]*\}\s*\)"
    
    # Pattern 3: await request({ url: '/api/v1/...', method: '...' })
    pattern3 = r"await\s+request\s*\(\s*\{[^}]*url\s*:\s*['\"]/api/v1/[^'\"]+['\"][^}]*method\s*:\s*['\"]([A-Z]+)['\"][^}]*\}\s*\)"
    
    # Pattern 4: await request({ url: '/api/v1/...', method: '...' })
    pattern4 = r"await\s+request\s*\(\s*\{[^}]*url\s*:\s*['\"]/api/v1/[^'\"]+['\"][^}]*\}\s*\)"

    matches = []
    
    for pattern in [pattern1, pattern2, pattern3, pattern4]:
        compiled = re.compile(pattern)
        for match in compiled.finditer(content):
            url_match = None
            method_match = None
            
            # Extract URL (group 0 or 1 depending on pattern)
            if 'url' in content[match.start():match.end()]:
                url_search = re.search(r"url\s*:\s*['\"](/api/v1/[^'\"]+)['\"]", match.group(0))
                if url_search:
                    url_match = url_search.group(1)
            
            # Extract method (group 2 or 3 depending on pattern)
            method_search = re.search(r"method\s*:\s*['\"]([A-Z]+)['\"]", match.group(0))
            if method_search:
                method_match = method_search.group(1).upper()
            
            if url_match:
                matches.append({
                    'file': file_path,
                    'url': url_match,
                    'method': method_match or 'GET',  # Default to GET if not specified
                    'line': content[:match.start()].count('\n') + 1
                })
    
    return matches

def main():
    frontend_dir = '../miniprogram-1/miniprogram'
    ts_files = find_ts_files(frontend_dir)
    print(f"Found {len(ts_files)} TS files\n")
    
    all_matches = []
    for file_path in sorted(ts_files):
        matches = extract_api_calls_v2(file_path)
        if matches:
            print(f"=== {file_path} ===")
            print(f"Found {len(matches)} API calls")
            for match in matches:
                print(f"  {match['method']} {match['url']} (line {match['line']})")
            all_matches.extend(matches)
    
    print(f"\n=== TOTAL API CALLS FOUND: {len(all_matches)} ===")

if __name__ == '__main__':
    main()
