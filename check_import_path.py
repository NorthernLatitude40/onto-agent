"""
Check what the actual import path is for vehicle_repo in vehicle_routes
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

# Import the module to see its actual name
from src.api.v1.endpoints.controller import vehicle_routes

print(f"Module name: {vehicle_routes.__name__}")
print(f"vehicle_repo module: {vehicle_routes.vehicle_repo.__name__}")
print(f"list_vehicles function: {vehicle_routes.vehicle_repo.list_vehicles}")
