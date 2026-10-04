#!/usr/bin/env python3
"""
Final integration readiness verification script.
Checks if backend and frontend endpoints match for successful integration testing.
"""
import re
from pathlib import Path

def extract_backend_endpoints():
    """Extract all API endpoints from backend Python files."""
    api_dir = Path('src/api/v1/endpoints')
    endpoints = []
    
    for api_file in sorted(api_dir.glob('*.py')):
        if not api_file.exists():
            continue
            
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all @router.get and @router.post decorators
        get_pattern = r'@router\.get\("([^"]+)"\)'
        post_pattern = r'@router\.post\("([^"]+)"\)'
        put_pattern = r'@router\.put\("([^"]+)"\)'
        delete_pattern = r'@router\.delete\("([^"]+)"\)'
        
        for match in re.finditer(get_pattern, content):
            path = match.group(1).strip()
            endpoints.append(('GET', path))
        
        for match in re.finditer(post_pattern, content):
            path = match.group(1).strip()
            endpoints.append(('POST', path))
        
        for match in re.finditer(put_pattern, content):
            path = match.group(1).strip()
            endpoints.append(('PUT', path))
        
        for match in re.finditer(delete_pattern, content):
            path = match.group(1).strip()
            endpoints.append(('DELETE', path))
    
    return endpoints

def extract_frontend_api_calls():
    """Extract all API calls from frontend TypeScript files."""
    api_calls = []
    frontend_dir = Path('./miniprogram-1/miniprogram')
    
    # Find all .ts files
    ts_files = list(frontend_dir.rglob('*.ts'))
    
    for ts_file in sorted(ts_files):
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all /api/v1/... URLs
        # Pattern: url: '/api/v1/...' or url: "/api/v1/..."
        pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        matches = re.findall(pattern, content)
        
        # Find method and URL together
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
    print("INTEGRATION READINESS VERIFICATION")
    print("=" * 80)
    
    # Extract backend endpoints
    print("\n1. Extracting backend API endpoints...")
    backend_endpoints = extract_backend_endpoints()
    backend_map = {}
    for method, path in backend_endpoints:
        if path not in backend_map:
            backend_map[path] = []
        backend_map[path].append(method)
    
    print(f"   Total backend endpoints: {len(backend_endpoints)}")
    for path in sorted(backend_map.keys()):
        methods = ', '.join(sorted(set(backend_map[path])))
        print(f"      {methods} /api/v1/{path}")
    
    # Extract frontend API calls
    print("\n2. Extracting frontend API calls...")
    frontend_calls = extract_frontend_api_calls()
    frontend_map = {}
    for method, path in frontend_calls:
        if path not in frontend_map:
            frontend_map[path] = []
        frontend_map[path].append(method)
    
    print(f"   Total frontend API calls: {len(frontend_calls)}")
    for path in sorted(frontend_map.keys()):
        methods = ', '.join(sorted(set(frontend_map[path])))
        print(f"      {methods} /api/v1/{path}")
    
    # Check consistency
    print("\n3. Checking API consistency...")
    
    # Frontend calls without backend endpoints
    missing_in_backend = []
    for path in sorted(frontend_map.keys()):
        if path not in backend_map:
            missing_in_backend.append(path)
    
    # Backend endpoints not used by frontend
    unused_in_frontend = []
    for path in sorted(backend_map.keys()):
        if path not in frontend_map:
            unused_in_frontend.append(path)
    
    # Check method consistency for matching paths
    method_mismatches = []
    for path in sorted(set(frontend_map.keys()) & set(backend_map.keys())):
        frontend_methods = set(frontend_map[path])
        backend_methods = set(backend_map[path])
        if frontend_methods != backend_methods:
            method_mismatches.append((path, frontend_methods, backend_methods))
    
    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)
    
    # Report missing endpoints
    if missing_in_backend:
        print(f"\n❌ FRONTEND CALLS WITHOUT BACKEND ENDPOINTS ({len(missing_in_backend)}):")
        for path in sorted(missing_in_backend):
            methods = ', '.join(sorted(set(frontend_map[path])))
            print(f"   - {methods} /api/v1/{path}")
    else:
        print("\n✅ All frontend API calls have corresponding backend endpoints")
    
    # Report unused endpoints
    if unused_in_frontend:
        print(f"\n⚠️  BACKEND ENDPOINTS NOT USED BY FRONTEND ({len(unused_in_frontend)}):")
        for path in sorted(unused_in_frontend):
            methods = ', '.join(sorted(set(backend_map[path])))
            print(f"   - {methods} /api/v1/{path}")
    else:
        print("\n✅ All backend endpoints are used by the frontend")
    
    # Report method mismatches
    if method_mismatches:
        print(f"\n⚠️  METHOD MISMATCHES ({len(method_mismatches)}):")
        for path, frontend_methods, backend_methods in method_mismatches:
            print(f"   - /api/v1/{path}")
            print(f"     Frontend: {', '.join(sorted(frontend_methods))}")
            print(f"     Backend:  {', '.join(sorted(backend_methods))}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    total_backend = len(backend_endpoints)
    total_frontend = len(frontend_calls)
    matching_paths = len(set(backend_map.keys()) & set(frontend_map.keys()))
    
    print(f"Total backend endpoints: {total_backend}")
    print(f"Total frontend API calls: {total_frontend}")
    print(f"Matching endpoint paths: {matching_paths}")
    print(f"Missing in backend: {len(missing_in_backend)}")
    print(f"Unused in frontend: {len(unused_in_frontend)}")
    print(f"Method mismatches: {len(method_mismatches)}")
    
    # Integration testing status
    print("\n" + "=" * 80)
    print("INTEGRATION TESTING STATUS:")
    print("=" * 80)
    
    if not missing_in_backend and not method_mismatches:
        print("✅ INTEGRATION READY: All frontend API calls have matching backend endpoints")
        print("   Integration testing should pass successfully.")
    else:
        print("❌ INTEGRATION NOT READY:")
        if missing_in_backend:
            print(f"   - {len(missing_in_backend)} frontend API calls need backend implementation")
        if method_mismatches:
            print(f"   - {len(method_mismatches)} endpoints have HTTP method mismatches")
        print("\n   Integration testing will FAIL until these issues are resolved.")
    
    return len(missing_in_backend) + len(method_mismatches)

if __name__ == '__main__':
    exit_code = main()
    exit(exit_code)
