"""Debug script to understand why patching isn't working"""
import sys
from unittest.mock import patch, MagicMock

# Check what's in sys.modules before importing
print("=== Before any imports ===")
print(f"'src.api.v1.endpoints.dao.vehicle_repo' in sys.modules: {'src.api.v1.endpoints.dao.vehicle_repo' in sys.modules}")

# Now import vehicle_routes
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_router

print("\n=== After importing vehicle_routes ===")
print(f"'src.api.v1.endpoints.dao.vehicle_repo' in sys.modules: {'src.api.v1.endpoints.dao.vehicle_repo' in sys.modules}")

# Check what vehicle_repo is
from src.api.v1.endpoints.controller import vehicle_routes
print(f"\n=== vehicle_routes module ===")
print(f"vehicle_routes.vehicle_repo: {vehicle_routes.vehicle_repo}")
print(f"Type: {type(vehicle_routes.vehicle_repo)}")

# Try to patch it
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
    print("\n=== Inside patch context ===")
    print(f"mock_list: {mock_list}")
    
    # Call the function directly
    result = vehicle_routes.get_stored_vehicles()
    print(f"Result from get_stored_vehicles(): {result}")
    print(f"Mock called: {mock_list.called}")
