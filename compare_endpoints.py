#!/usr/bin/env python3
"""
Comprehensive endpoint comparison between frontend and backend.
"""
import re
from pathlib import Path

def extract_backend_endpoints():
    """Extract all API endpoints from backend Python files."""
    endpoints = []
    
    api_dir = Path('src/api/v1/endpoints')
    for api_file in api_dir.glob('*.py'):
        if not api_file.exists():
            continue
            
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all @router.get and @router.post decorators
        get_pattern = r'@router\.get\("([^"]+)"\)'
        post_pattern = r'@router\.post\("([^"]+)"\)'
        
        for match in re.finditer(get_pattern, content):
            path = match.group(1).strip()
            # Remove leading slash if present
            if path.startswith('/'):
                path = path[1:]
            endpoints.append(('GET', path))
        
        for match in re.finditer(post_pattern, content):
            path = match.group(1).strip()
            # Remove leading slash if present
            if path.startswith('/'):
                path = path[1:]
            endpoints.append(('POST', path))
    
    return endpoints

def extract_frontend_api_calls():
    """Extract all API calls from frontend TypeScript files."""
    api_calls = []
    
    # Find all .ts files in the miniprogram directory
    ts_files = list(Path('./miniprogram-1/miniprogram').rglob('*.ts'))
    
    for ts_file in ts_files:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all /api/v1/... URLs
        pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        matches = re.findall(pattern, content)
        
        # Also look for method + url patterns
        method_pattern = r"method:\s*['\"](GET|POST|PUT|DELETE|PATCH)['\"].*?url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        method_matches = re.findall(method_pattern, content, re.DOTALL)
        
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
    
    return api_calls

def main():
    print("=" * 80)
    print("COMPREHENSIVE API ENDPOINT COMPARISON")
    print("=" * 80)
    
    # Extract backend endpoints
    print("\n1. Backend Endpoints:")
    backend_endpoints = extract_backend_endpoints()
    backend_map = {path: method for method, path in backend_endpoints}
    
    for method, path in sorted(backend_endpoints):
        print(f"   {method:6} /api/v1/{path}")
    
    # Extract frontend API calls
    print("\n2. Frontend API Calls:")
    frontend_calls = extract_frontend_api_calls()
    frontend_map = {path: method for method, path in frontend_calls}
    
    for method, path in sorted(frontend_calls):
        print(f"   {method:6} /api/v1/{path}")
    
    # Find mismatches
    print("\n3. Analysis:")
    print("=" * 80)
    
    # Frontend calls without backend endpoints
    missing_in_backend = []
    for path in frontend_map:
        if path not in backend_map:
            missing_in_backend.append((frontend_map[path], path))
    
    if missing_in_backend:
        print(f"\n❌ Frontend calls WITHOUT backend endpoints ({len(missing_in_backend)}):")
        for method, path in sorted(missing_in_backend):
            print(f"   {method:6} /api/v1/{path}")
    else:
        print("\n✅ All frontend API calls have corresponding backend endpoints")
    
    # Backend endpoints not used by frontend
    unused_in_frontend = []
    for path in backend_map:
        if path not in frontend_map:
            unused_in_frontend.append((backend_map[path], path))
    
    if unused_in_frontend:
        print(f"\n⚠️  Backend endpoints NOT used by frontend ({len(unused_in_frontend)}):")
        for method, path in sorted(unused_in_frontend):
            print(f"   {method:6} /api/v1/{path}")
    else:
        print("\n✅ All backend endpoints are used by the frontend")
    
    # Matching endpoints
    matching = []
    for path in set(backend_map.keys()) & set(frontend_map.keys()):
        backend_method = backend_map[path]
        frontend_method = frontend_map[path]
        if backend_method == frontend_method:
            matching.append((backend_method, path))
    
    print(f"\n✅ Matching endpoints (same method): {len(matching)}")
    for method, path in sorted(matching):
        print(f"   {method:6} /api/v1/{path}")
    
    # Method mismatches
    method_mismatches = []
    for path in set(backend_map.keys()) & set(frontend_map.keys()):
        backend_method = backend_map[path]
        frontend_method = frontend_map[path]
        if backend_method != frontend_method:
            method_mismatches.append((backend_method, frontend_method, path))
    
    if method_mismatches:
        print(f"\n⚠️  Method mismatches ({len(method_mismatches)}):")
        for backend_method, frontend_method, path in sorted(method_mismatches):
            print(f"   Backend: {backend_method:6} | Frontend: {frontend_method:6} | /api/v1/{path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total backend endpoints: {len(backend_endpoints)}")
    print(f"Total frontend API calls: {len(frontend_calls)}")
    print(f"Matching endpoints (method + path): {len(matching)}")
    print(f"Missing in backend: {len(missing_in_backend)}")
    print(f"Unused in frontend: {len(unused_in_frontend)}")
    print(f"Method mismatches: {len(method_mismatches)}")
    
    total_issues = len(missing_in_backend) + len(unused_in_frontend) + len(method_mismatches)
    if total_issues == 0:
        print("\n🎉 PERFECT CONSISTENCY! All endpoints match.")
    else:
        print(f"\n⚠️  TOTAL INCONSISTENCIES: {total_issues}")

if __name__ == '__main__':
    main()