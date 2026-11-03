#!/usr/bin/env python3
"""
Script to verify the cause of duplicate routes.
This script checks if shop_router is included multiple times with different prefixes.
"""

import sys
from fastapi import FastAPI
from src.api.v1.router import api_v1_router
from src.modules.scraper.router import router as scraper_router

def collect_all_routes(app, prefix="", routes=None):
    """Recursively collect all routes from a FastAPI app or router."""
    if routes is None:
        routes = []
    
    for route in app.routes:
        # Skip WebSocket routes
        if hasattr(route, 'path') and route.path.startswith('/ws'):
            continue
            
        # Handle included routers
        if hasattr(route, 'include_context'):
            ctx = route.include_context
            new_prefix = prefix + (ctx.prefix if ctx.prefix else "")
            collect_all_routes(ctx.routes, new_prefix, routes)
        else:
            full_path = prefix + route.path
            routes.append({
                'path': full_path,
                'method': route.methods,
                'source': 'routing' if hasattr(route, 'include_context') else 'direct'
            })
    
    return routes

def main():
    # Create a FastAPI app like agent_server does
    app = FastAPI(title="Test API Gateway")
    
    # Include routers exactly as agent_server.py does
    from src.api.auth_api import router as auth_router
    from src.api.dashboard_api import dashboard_router, shop_router
    from src.api.agent_api import router
    
    app.include_router(router)
    app.include_router(api_v1_router)  # This includes /api/v1/shop via v1/router.py
    app.include_router(dashboard_router)
    app.include_router(shop_router)     # This directly includes /api/v1/shop again!
    app.include_router(auth_router)
    app.include_router(scraper_router)
    
    # Collect all routes
    all_routes = collect_all_routes(app)
    
    # Find duplicates
    path_map = {}
    for route in all_routes:
        key = (route['path'], tuple(sorted(route['method'])))
        if key not in path_map:
            path_map[key] = []
        path_map[key].append(route)
    
    # Report duplicates
    print("=" * 80)
    print("DUPLICATE ROUTES FOUND:")
    print("=" * 80)
    
    duplicates_found = False
    for key, routes in path_map.items():
        if len(routes) > 1:
            duplicates_found = True
            path, methods = key
            print(f"\nPath: {path}")
            print(f"Methods: {', '.join(methods)}")
            print(f"Occurrences: {len(routes)}")
            for i, route in enumerate(routes, 1):
                print(f"  {i}. Source: {route['source']}")
    
    if not duplicates_found:
        print("\nNo duplicate routes found.")
    
    # Specifically check for shop routes
    print("\n" + "=" * 80)
    print("SHOP-RELATED ROUTES:")
    print("=" * 80)
    
    shop_routes = [r for r in all_routes if '/shop/' in r['path'] or r['path'].endswith('/shop')]
    for route in sorted(shop_routes, key=lambda x: x['path']):
        print(f"{route['method']} {route['path']}")

if __name__ == "__main__":
    main()