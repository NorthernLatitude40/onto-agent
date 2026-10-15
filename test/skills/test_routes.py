#!/usr/bin/env python
"""Test script to verify scraper routes."""
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
    print("Checking scraper_router directly:")
    from src.modules.scraper.router import router as scraper_router
    print(f"  Routes: {[r.path for r in scraper_router.routes]}")
    
    print("\nChecking api_v1_router:")
    all_routes = get_all_routes(api_v1_router)
    print(f"  Total routes: {len(all_routes)}")
    
    scraper_routes = [r for r in all_routes if '/scraper/' in r]
    print(f"\nFound {len(scraper_routes)} scraper routes:")
    for route in scraper_routes:
        print(f"  - {route}")

if __name__ == '__main__':
    all_routes = get_all_routes(api_v1_router)
    
    print('All v1 API routes:')
    for route in sorted(all_routes):
        if 'scraper' in route:
            print(f'  >>> {route}')
        else:
            print(f'     {route}')
    
    scraper_routes = [r for r in all_routes if '/scraper/' in r]
    
    print(f'\nFound {len(scraper_routes)} scraper routes:')
    for route in scraper_routes:
        print(f"  - {route}")
    
    # Check for duplicates
    unique_routes = set(scraper_routes)
    if len(scraper_routes) != len(unique_routes):
        print('\n⚠️  WARNING: Duplicate routes found!')
    else:
        print(f'\n✅ All {len(scraper_routes)} scraper routes are unique')