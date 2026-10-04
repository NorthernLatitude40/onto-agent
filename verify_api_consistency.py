#!/usr/bin/env python3
"""
Comprehensive API consistency verification script.
Checks if backend and frontend endpoints match for integration testing.
"""
import re
from pathlib import Path
from typing import Set, Dict, List, Tuple

def extract_backend_endpoints() -> Set[str]:
    """Extract all backend API endpoints from FastAPI router definitions."""
    backend_dir = Path('./src/api/v1/endpoints')
    endpoints = set()
    
    for py_file in backend_dir.glob('*.py'):
        content = py_file.read_text()
        
        # Match router.get, router.post, router.put, router.delete, router.patch
        pattern = r'@router\.(get|post|put|delete|patch)\(["\'](/api/v1(?:[^"\']*))["\'][^)]*\)'
        matches = re.findall(pattern, content)
        
        for method, path in matches:
            # Clean up the path
            path = path.replace('{', '<').replace('}', '>')
            endpoints.add(path)
    
    return endpoints

def extract_frontend_api_calls() -> Set[str]:
    """Extract all API calls from frontend TypeScript files."""
    api_calls = set()
    frontend_dir = Path('../miniprogram-1/miniprogram')
    
    for ts_file in frontend_dir.rglob('*.ts'):
        content = ts_file.read_text()
        
        # Match request calls with URL patterns
        pattern = r"request\s*\(\s*\{[^}]*url\s*:\s*['\"](/api/v1[^'\"]*)['\"][^}]*\}\s*\)"
        matches = re.findall(pattern, content)
        
        for path in matches:
            # Clean up query parameters
            if '?' in path:
                path = path.split('?')[0]
            api_calls.add(path)
    
    return api_calls

def check_endpoint_coverage(backend: Set[str], frontend: Set[str]) -> Tuple[Set[str], Set[str]]:
    """
    Check which backend endpoints are covered by frontend calls.
    Returns (covered, uncovered) where:
    - covered: endpoints that exist in both backend and frontend
    - uncovered: backend endpoints not called by frontend
    """
    # Normalize paths for comparison
    def normalize(path):
        # Remove trailing slashes
        path = path.rstrip('/')
        return path
    
    covered = set()
    uncovered = set()
    
    for be_path in backend:
        norm_be = normalize(be_path)
        found = False
        
        # Try exact match first
        if any(normalize(fe_path) == norm_be for fe_path in frontend):
            covered.add(norm_be)
            found = True
        else:
            # Try to find a matching pattern (handle parameterized routes)
            be_parts = norm_be.split('/')
            for fe_path in frontend:
                fe_parts = normalize(fe_path).split('/')
                if len(be_parts) != len(fe_parts):
                    continue
                
                match = True
                for be_p, fe_p in zip(be_parts, fe_parts):
                    # If both are parameters (<param>), they match
                    if be_p.startswith('<') and be_p.endswith('>'):
                        continue
                    if fe_p.startswith('<') and fe_p.endswith('>'):
                        continue
                    # Otherwise they must be identical
                    if be_p != fe_p:
                        match = False
                        break
                
                if match:
                    covered.add(norm_be)
                    found = True
                    break
        
        if not found:
            uncovered.add(norm_be)
    
    return covered, uncovered

def check_frontend_coverage(backend: Set[str], frontend: Set[str]) -> Tuple[Set[str], Set[str]]:
    """
    Check which frontend API calls have corresponding backend endpoints.
    Returns (valid, invalid) where:
    - valid: frontend calls that match backend endpoints
    - invalid: frontend calls without backend endpoints
    """
    # Normalize paths for comparison
    def normalize(path):
        path = path.rstrip('/')
        return path
    
    valid = set()
    invalid = set()
    
    for fe_path in frontend:
        norm_fe = normalize(fe_path)
        found = False
        
        # Try exact match first
        if any(normalize(be_path) == norm_fe for be_path in backend):
            valid.add(norm_fe)
            found = True
        else:
            # Try to find a matching pattern (handle parameterized routes)
            fe_parts = norm_fe.split('/')
            for be_path in backend:
                be_parts = normalize(be_path).split('/')
                if len(be_parts) != len(fe_parts):
                    continue
                
                match = True
                for fe_p, be_p in zip(fe_parts, be_parts):
                    # If both are parameters (<param>), they match
                    if fe_p.startswith('<') and fe_p.endswith('>'):
                        continue
                    if be_p.startswith('<') and be_p.endswith('>'):
                        continue
                    # Otherwise they must be identical
                    if fe_p != be_p:
                        match = False
                        break
                
                if match:
                    valid.add(norm_fe)
                    found = True
                    break
        
        if not found:
            invalid.add(norm_fe)
    
    return valid, invalid

def generate_report(backend: Set[str], frontend: Set[str]) -> str:
    """Generate a comprehensive API consistency report."""
    covered_backend, uncovered_backend = check_endpoint_coverage(backend, frontend)
    valid_frontend, invalid_frontend = check_frontend_coverage(backend, frontend)
    
    report = []
    report.append("# API Consistency Verification Report")
    report.append("=" * 60)
    report.append()
    
    # Summary
    report.append("## Executive Summary")
    report.append(f"- Total backend endpoints: {len(backend)}")
    report.append(f"- Total frontend API calls: {len(frontend)}")
    report.append(f"- Backend endpoints covered by frontend: {len(covered_backend)} ({len(covered_backend)/len(backend)*100:.1f}%)")
    report.append(f"- Frontend calls with backend support: {len(valid_frontend)} ({len(valid_frontend)/len(frontend)*100:.1f}%)")
    report.append()
    
    # Integration testing status
    report.append("## Integration Testing Status")
    if len(invalid_frontend) == 0 and len(uncovered_backend) < 5:
        report.append("✅ **READY FOR INTEGRATION TESTING**")
        report.append("All frontend API calls have corresponding backend endpoints.")
    else:
        report.append("⚠️ **INTEGRATION TESTING MAY FAIL**")
        if len(invalid_frontend) > 0:
            report.append(f"Frontend is calling {len(invalid_frontend)} endpoints that don't exist on the backend.")
        if len(uncovered_backend) > 0:
            report.append(f"Backend has {len(uncovered_backend)} endpoints not used by frontend (may be OK).")
    report.append()
    
    # Detailed findings
    if invalid_frontend:
        report.append("### ❌ Frontend Calls Without Backend Endpoints")
        for path in sorted(invalid_frontend):
            report.append(f"  - {path}")
        report.append()
    
    if uncovered_backend:
        report.append("### ℹ️ Backend Endpoints Not Used by Frontend")
        for path in sorted(uncovered_backend):
            report.append(f"  - {path}")
        report.append()
    
    if valid_frontend:
        report.append("### ✅ Valid Frontend-Backend Matches")
        for path in sorted(valid_frontend):
            report.append(f"  - {path}")
        report.append()
    
    return "\n".join(report)

def main():
    print("Extracting backend endpoints...")
    backend_endpoints = extract_backend_endpoints()
    print(f"Found {len(backend_endpoints)} backend endpoints")
    print()
    
    print("Extracting frontend API calls...")
    frontend_calls = extract_frontend_api_calls()
    print(f"Found {len(frontend_calls)} unique frontend API calls")
    print()
    
    report = generate_report(backend_endpoints, frontend_calls)
    print(report)
    
    # Save to file
    with open('api_consistency_verification.md', 'w') as f:
        f.write(report)
    
    print("\nReport saved to api_consistency_verification.md")

if __name__ == '__main__':
    main()
