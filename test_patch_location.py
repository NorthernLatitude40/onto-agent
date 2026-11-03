"""Test different patch locations"""
from unittest.mock import patch
import sys

# Test 1: Patch at the point of use (inside vehicle_routes)
print("=== Test 1: Patching inside vehicle_routes module ===")
with patch('src.api.v1.endpoints.controller.vehicle_routes.vehicle_repo.list_vehicles') as mock_list:
    from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
    mock_list.return_value = [{"test": "data"}]
    result = get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Mock called: {mock_list.called}\n")

# Test 2: Patch at the DAO level (original approach)
print("=== Test 2: Patching at DAO level ===")
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
    from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
    mock_list.return_value = [{"test": "data2"}]
    result = get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Mock called: {mock_list.called}\n")
