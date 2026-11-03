#!/usr/bin/env python3
"""
Check for duplicate routes across all v1 API endpoints.
"""
from src.api.v1.router import api_v1_router

def get_all_routes(router, prefix=''):
    """Recursively get all routes from a FastAPI router."""
    routes = []
    for route in router.routes:
        if hasattr(route, 'path'):
            full_path = prefix + route.path
            routes.append(full_path)
        elif hasattr(route, 'include_context'):
            # This is an included router via include_router()
            ctx = route.include_context
            app_prefix = getattr(ctx.included_router, 'prefix', '')
            full_prefix = prefix + ctx.prefix + app_prefix
            routes.extend(get_all_routes(ctx.included_router, full_prefix))
    return routes

if __name__ == '__main__':
    all_routes = get_all_routes(api_v1_router)
    
    print(f"Total routes: {len(all_routes)}")
    print()
    
    # Find duplicates
    route_counts = {}
    for route in all_routes:
        route_counts[route] = route_counts.get(route, 0) + 1
    
    duplicates = {k: v for k, v in route_counts.items() if v > 1}
    unique_routes = {k: v for k, v in route_counts.items() if v == 1}
    
    print(f"Unique routes: {len(unique_routes)}")
    print(f"Duplicate routes: {len(duplicates)}")
    print()
    
    if duplicates:
        print("DUPLICATE ROUTES:")
        for route, count in sorted(duplicates.items()):
            print(f"  {route} (appears {count} times)")
        print()
    
    # Check scraper routes specifically
    scraper_routes = [r for r in all_routes if '/scraper/' in r]
    print(f"Scraper routes: {len(scraper_routes)}")
    for route in sorted(scraper_routes):
        count = route_counts[route]
        marker = " ⚠️ DUPLICATE" if count > 1 else " ✓"
        print(f"  {marker} {route}")
