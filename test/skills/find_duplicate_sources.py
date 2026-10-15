#!/usr/bin/env python3
"""
Find which modules are contributing to duplicate routes.
"""
from src.api.v1.router import api_v1_router

def get_all_routes_with_source(router, prefix='', source_name=None):
    """Recursively get all routes with their source module."""
    routes = []
    for route in router.routes:
        if hasattr(route, 'path'):
            full_path = prefix + route.path
            routes.append((full_path, source_name or 'unknown'))
        elif hasattr(route, 'include_context'):
            ctx = route.include_context
            app_prefix = getattr(ctx.included_router, 'prefix', '')
            full_prefix = prefix + ctx.prefix + app_prefix
            # Try to get the module name from the router
            router_module = getattr(ctx.included_router, '__module__', None)
            if router_module:
                source = router_module.split('.')[-1]  # Get last part of module path
            else:
                source = source_name or 'unknown'
            routes.extend(get_all_routes_with_source(
                ctx.included_router, 
                full_prefix, 
                source
            ))
    return routes

if __name__ == '__main__':
    all_routes = get_all_routes_with_source(api_v1_router)
    
    # Group by route path
    route_to_sources = {}
    for route, source in all_routes:
        if route not in route_to_sources:
            route_to_sources[route] = []
        route_to_sources[route].append(source)
    
    # Find duplicates
    duplicates = {k: v for k, v in route_to_sources.items() if len(v) > 1}
    
    print("DUPLICATE ROUTES AND THEIR SOURCES:")
    print("=" * 60)
    for route, sources in sorted(duplicates.items()):
        print(f"\nRoute: {route}")
        print(f"  Sources: {', '.join(sorted(set(sources)))}")
        print(f"  Count: {len(sources)}")
