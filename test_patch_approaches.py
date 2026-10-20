"""
Test different patching approaches
"""
from unittest.mock import patch, MagicMock
import sys

# Test 1: Patch the module path
print("=== Test 1: Patching 'src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo' ===")
with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo') as mock_module:
    mock_module.list_vehicles.return_value = [{"test": "data"}]
    
    # Import after patching
    from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
    result = get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Called with: {mock_module.list_vehicles.called}")

# Test 2: Patch the function path
print("\n=== Test 2: Patching 'src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles' ===")
with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_func:
    mock_func.return_value = [{"test": "data2"}]
    
    # Import after patching
    from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
    result = get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Called with: {mock_func.called}")

# Test 3: Patch after importing (simulating what happens in tests)
print("\n=== Test 3: Import first, then patch ===")
from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_func:
    mock_func.return_value = [{"test": "data3"}]
    
    result = get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Called with: {mock_func.called}")

# Test 4: Patch the module attribute
print("\n=== Test 4: Patch vehicle_repo module ===")
from src.api.v1.endpoints.controller import vehicle_routes
with patch.object(vehicle_routes, 'vehicle_repo') as mock_module:
    mock_module.list_vehicles.return_value = [{"test": "data4"}]
    
    result = vehicle_routes.get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Called with: {mock_module.list_vehicles.called}")
