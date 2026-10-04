#!/usr/bin/env python3
"""
API Consistency Check Script
Checks if frontend and backend API endpoints are consistent.
"""
import re
import json
from pathlib import Path

def extract_backend_endpoints(file_path):
    """Extract all @router endpoints from a FastAPI file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all @router.decorator lines
    pattern = r'@router\.(post|get|put|delete|patch)\(["\']([^"\']+)["\'][^)]*\)'
    matches = re.findall(pattern, content)
    
    endpoints = []
    for method, path in matches:
        # Clean up the path
        clean_path = path.strip()
        if clean_path.startswith('/'):
            clean_path = clean_path[1:]  # Remove leading slash for consistency
        endpoints.append((method.upper(), clean_path))
    
    return endpoints

def extract_frontend_api_calls(directory):
    """Extract all API calls from frontend TypeScript files."""
    api_calls = []
    
    # Find all .ts files
    ts_files = list(Path(directory).rglob('*.ts'))
    
    for ts_file in ts_files:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all /api/v1/... URLs and their methods
        url_pattern = r"url:\s*['\"](/api/v1/[^'\"]+)['\"]"
        method_pattern = r"method:\s*['\"](GET|POST|PUT|DELETE|PATCH)['\"]"
        
        # Find all url occurrences
        url_matches = re.finditer(url_pattern, content)
        for match in url_matches:
            path = match.group(1)
            clean_path = path.strip()
            
            # Look backward and forward to find the method
            start_pos = match.start()
            end_pos = match.end()
            
            # Search backward for method (up to 500 chars)
            context_start = max(0, start_pos - 1000)
            context_end = min(len(content), end_pos + 1000)
            context = content[context_start:context_end]
            
            # Find method in the context
            method_match = re.search(method_pattern, context)
            if method_match:
                method = method_match.group(1).upper()
            else:
                method = 'GET'  # Default to GET if method not specified
            
            api_calls.append((method, clean_path))
    
    return api_calls

def main():
    print("=" * 80)
    print("API CONSISTENCY CHECK")
    print("=" * 80)
    
    # Extract backend endpoints
    print("\n1. Extracting backend API endpoints...")
    backend_file = 'src/api/v1/endpoints/inventory_api.py'
    backend_endpoints = extract_backend_endpoints(backend_file)
    print(f"   Found {len(backend_endpoints)} backend endpoints")
    
    # Extract frontend API calls
    print("\n2. Extracting frontend API calls...")
    frontend_dir = './miniprogram-1/miniprogram'
    frontend_calls = extract_frontend_api_calls(frontend_dir)
    print(f"   Found {len(frontend_calls)} frontend API calls")
    
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
            frontend_method = frontend_map[path]
            print(f"   - {frontend_method} /api/v1/{path}")
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