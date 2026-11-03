"""
Test to verify patch timing
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from unittest.mock import patch

# Test 1: Patch before importing the module
print("Test 1: Patching before import")
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
    mock_list.return_value = [{"test": "data"}]
    from src.api.v1.endpoints.controller import vehicle_routes
    result = vehicle_routes.get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Mock called: {mock_list.called}")

# Test 2: Patch after importing the module
print("\nTest 2: Patching after import")
from src.api.v1.endpoints.controller import vehicle_routes as vr2
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list2:
    mock_list2.return_value = [{"test": "data2"}]
    result2 = vr2.get_stored_vehicles()
    print(f"Result: {result2}")
    print(f"Mock called: {mock_list2.called}")
