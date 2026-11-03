"""
Debug script to test different patch approaches
"""
from unittest.mock import patch
import sys

# Test 1: Direct module path
print("\n=== Test 1: Direct module path ===")
try:
    with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_list:
        mock_list.return_value = [{"test": "data"}]
        from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
        result = get_stored_vehicles()
        print(f"Result: {result}")
        print(f"Mock called: {mock_list.called}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Relative import path from test perspective
print("\n=== Test 2: From src.api.v1.endpoints.controller.vehicle_routes ===")
try:
    with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_list:
        mock_list.return_value = [{"test": "data"}]
        from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
        result = get_stored_vehicles()
        print(f"Result: {result}")
        print(f"Mock called: {mock_list.called}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Check what vehicle_repo actually is
print("\n=== Test 3: Inspect vehicle_repo ===")
try:
    from src.api.v1.endpoints.controller.vehicle_routes import vehicle_repo
    print(f"vehicle_repo type: {type(vehicle_repo)}")
    print(f"vehicle_repo module: {vehicle_repo.__name__ if hasattr(vehicle_repo, '__name__') else 'N/A'}")
    print(f"vehicle_repo file: {vehicle_repo.__file__ if hasattr(vehicle_repo, '__file__') else 'N/A'}")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Try patching the actual module
print("\n=== Test 4: Patch vehicle_repo directly ===")
try:
    from src.api.v1.endpoints.controller import vehicle_routes
    with patch.object(vehicle_routes.vehicle_repo, 'list_vehicles') as mock_list:
        mock_list.return_value = [{"test": "data"}]
        result = vehicle_routes.get_stored_vehicles()
        print(f"Result: {result}")
        print(f"Mock called: {mock_list.called}")
except Exception as e:
    print(f"Error: {e}")
