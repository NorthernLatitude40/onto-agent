#!/usr/bin/env python3
"""
Comprehensive integration readiness verification script.
Checks if backend and mini-program endpoints match for successful integration testing.
"""
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

def extract_backend_endpoints():
    """Extract all backend API endpoints from the endpoints directory."""
    backend_file = Path("langgraph_workspace/src/api/v1/endpoints")
    
    if not backend_file.exists():
        return []
    
    # Get all Python files in the endpoints directory
    endpoint_files = list(backend_file.glob("*.py"))
    
    endpoints = []
    for file_path in endpoint_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find all @router.get and @router.post decorators
            get_pattern = r'@router\.get\("([^"]+)"\)'
            post_pattern = r'@router\.post\("([^"]+)"\)'
            
            gets = re.findall(get_pattern, content)
            posts = re.findall(post_pattern, content)
            
            for path in gets:
                endpoints.append(("GET", f"/api/v1{path}"))
            for path in posts:
                endpoints.append(("POST", f"/api/v1{path}"))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return endpoints

def extract_frontend_api_calls():
    """Extract all frontend API calls from the miniprogram directory."""
    frontend_dir = Path("miniprogram-1/miniprogram")
    
    if not frontend_dir.exists():
        return []
    
    # Find all .ts files
    ts_files = list(frontend_dir.glob("**/*.ts"))
    
    api_calls = set()
    
    for file_path in ts_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find request calls - look for patterns like request({ url: "..." })
            # This regex matches various ways of calling the API
            patterns = [
                r'url:\s*["\'](/api/v1[^"\']+)["\']',  # url: "/api/v1/..."
                r'request\(\s*{\s*url:\s*["\'](/api/v1[^"\']+)["\']',  # request({ url: "/api/v1/..." })
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    api_calls.add(match)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return sorted(api_calls)

def normalize_path(path: str) -> str:
    """Normalize path by removing query parameters and trailing slashes."""
    # Remove query parameters
    path = re.sub(r'\?.*$', '', path)
    # Remove trailing slashes
    path = path.rstrip('/')
    return path

def main():
    print("=" * 80)
    print("INTEGRATION READINESS VERIFICATION")
    print("=" * 80)
    print()
    
    # Extract endpoints
    print("1. Extracting backend API endpoints...")
    backend_endpoints = extract_backend_endpoints()
    print(f"   Found {len(backend_endpoints)} backend endpoints")
    print()
    
    print("2. Extracting frontend API calls...")
    frontend_calls = extract_frontend_api_calls()
    print(f"   Found {len(frontend_calls)} unique frontend API calls")
    print()
    
    # Normalize and organize
    backend_paths = set(normalize_path(path) for _, path in backend_endpoints)
    frontend_paths = set(normalize_path(path) for path in frontend_calls)
    
    # Find matches
    matching_paths = backend_paths & frontend_paths
    
    # Find mismatches
    missing_backend = frontend_paths - backend_paths
    unused_backend = backend_paths - frontend_paths
    
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    print(f"📊 Total Backend Endpoints: {len(backend_endpoints)}")
    print(f"📊 Total Frontend API Calls: {len(frontend_calls)}")
    print(f"📊 Matching Endpoints: {len(matching_paths)}")
    print()
    
    # Detailed results
    if len(matching_paths) > 0:
        print("✅ MATCHING ENDPOINTS:")
        for path in sorted(matching_paths):
            print(f"   {path}")
        print()
    
    if len(missing_backend) > 0:
        print("❌ FRONTEND CALLS WITHOUT BACKEND ENDPOINTS:")
        for path in sorted(missing_backend):
            print(f"   {path}")
        print()
    
    if len(unused_backend) > 0:
        print("⚠️  BACKEND ENDPOINTS NOT USED BY FRONTEND:")
        for path in sorted(unused_backend):
            print(f"   {path}")
        print()
    
    # Integration testing verdict
    print("=" * 80)
    print("INTEGRATION TESTING VERDICT")
    print("=" * 80)
    
    if len(matching_paths) == len(frontend_calls):
        print("✅ PASS: All frontend API calls have corresponding backend endpoints.")
        print("   Integration testing can proceed successfully.")
    else:
        print("❌ FAIL: Frontend and backend endpoints do not match.")
        print(f"   {len(missing_backend)} frontend API calls are missing backend implementations.")
        print()
        print("   Integration testing CANNOT pass until these mismatches are resolved.")
    
    print()

if __name__ == "__main__":
    main()
