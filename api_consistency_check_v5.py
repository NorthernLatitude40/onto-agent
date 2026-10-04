#!/usr/bin/env python3
"""
API Consistency Check - Final version with proper path handling.
"""
import re
from pathlib import Path

def extract_backend_endpoints(file_path):
    """Extract all API endpoints from backend Python files."""
    endpoints = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
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

def extract_frontend_api_calls(directory):
    """Extract all API calls from frontend TypeScript files."""
    api_calls = []
    
    # Find all .ts files in the pages directory
    print(f"DEBUG: Looking for TS files in {directory}")
    ts_files = list(Path(directory).rglob('*.ts'))
    print(f"DEBUG: Found {len(ts_files)} TS files")
    
    for ts_file in ts_files:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all /api/v1/... URLs - look for url: '/api/v1/...' or url: "/api/v1/..."
        pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        matches = re.findall(pattern, content)
        print(f"DEBUG: File {ts_file}, found {len(matches)} simple URL matches")
        
        # Also look for url: '/api/v1/...' with method
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
    print("API CONSISTENCY CHECK - FINAL VERSION")
    print("=" * 80)
    
    # Extract backend endpoints from all API files
    print("\n1. Extracting backend API endpoints...")
    api_dir = Path('src/api/v1/endpoints')
    backend_endpoints = []
    
    for api_file in api_dir.glob('*.py'):
        if api_file.exists():
            endpoints = extract_backend_endpoints(str(api_file))
            backend_endpoints.extend(endpoints)
            print(f"   Found {len(endpoints)} endpoints in {api_file.name}")
    
    print(f"\n   Total backend endpoints: {len(backend_endpoints)}")
    for method, path in sorted(backend_endpoints):
        print(f"      {method} /api/v1/{path}")
    
    # Extract frontend API calls
    print("\n2. Extracting frontend API calls...")
    frontend_dir = './miniprogram-1/miniprogram'
    frontend_calls = extract_frontend_api_calls(frontend_dir)
    print(f"   Found {len(frontend_calls)} frontend API calls")
    for method, path in sorted(frontend_calls):
        print(f"      {method} /api/v1/{path}")
    
    # Create mappings
    backend_map = {path: method for method, path in backend_endpoints}
    frontend_map = {path: method for method, path in frontend_calls}
    
    print("\n3. Checking consistency...")
    
    # Check for frontend calls that don't exist in backend
    missing_in_backend = []
    for path in frontend_map:
        if path not in backend_map:
            missing_in_backend.append(path)
    
    # Check for backend endpoints not called by frontend
    unused_in_frontend = []
    for path in backend_map:
        if path not in frontend_map:
            unused_in_frontend.append(path)
    
    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)
    
    # Report missing endpoints
    if missing_in_backend:
        print(f"\n❌ FRONTEND CALLS WITHOUT BACKEND ENDPOINTS ({len(missing_in_backend)}):")
        for path in sorted(missing_in_backend):
            method = frontend_map[path]
            print(f"   - {method} /api/v1/{path}")
    else:
        print("\n✅ All frontend API calls have corresponding backend endpoints")
    
    # Report unused endpoints
    if unused_in_frontend:
        print(f"\n⚠️  BACKEND ENDPOINTS NOT USED BY FRONTEND ({len(unused_in_frontend)}):")
        for path in sorted(unused_in_frontend):
            method = backend_map[path]
            print(f"   - {method} /api/v1/{path}")
    else:
        print("\n✅ All backend endpoints are used by the frontend")
    
    # Detailed comparison
    print("\n" + "=" * 80)
    print("DETAILED ENDPOINT COMPARISON:")
    print("=" * 80)
    
    all_paths = set(backend_map.keys()) | set(frontend_map.keys())
    for path in sorted(all_paths):
        backend_method = backend_map.get(path, 'N/A')
        frontend_method = frontend_map.get(path, 'N/A')
        status = "✅" if backend_method != 'N/A' and frontend_method != 'N/A' else "❌"
        print(f"{status} /api/v1/{path}")
        print(f"   Backend: {backend_method}")
        print(f"   Frontend: {frontend_method}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    total_backend = len(backend_endpoints)
    total_frontend = len(frontend_calls)
    matching = len(set(backend_map.keys()) & set(frontend_map.keys()))
    
    print(f"Total backend endpoints: {total_backend}")
    print(f"Total frontend API calls: {total_frontend}")
    print(f"Matching endpoints: {matching}")
    print(f"Missing in backend: {len(missing_in_backend)}")
    print(f"Unused in frontend: {len(unused_in_frontend)}")
    
    if not missing_in_backend and not unused_in_frontend:
        print("\n🎉 PERFECT CONSISTENCY! All endpoints match.")
    else:
        print(f"\n⚠️  INCONSISTENCIES FOUND: {len(missing_in_backend) + len(unused_in_frontend)} issues")

if __name__ == '__main__':
    main()