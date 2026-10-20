"""Test if import order matters"""
from unittest.mock import patch
import sys

# Clear any cached imports
modules_to_clear = [k for k in sys.modules.keys() if 'vehicle_repo' in k or 'vehicle_routes' in k]
for mod in modules_to_clear:
    del sys.modules[mod]

print("=== Test with fresh import ===")
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
    # Import AFTER the patch is set up
    from src.api.v1.endpoints.controller.vehicle_routes import get_stored_vehicles
    
    mock_list.return_value = [{"test": "data"}]
    result = get_stored_vehicles()
    print(f"Result: {result}")
    print(f"Mock called: {mock_list.called}")
