"""Debug script to understand TestClient behavior with patches"""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys

# Create a simple app
from fastapi import FastAPI, APIRouter

router = APIRouter()

@router.get("/test")
def test_endpoint():
    from src.api.v1.endpoints.dao.vehicle_repo import list_vehicles
    return list_vehicles()

app = FastAPI()
app.include_router(router, prefix="/api/v1")

# Create test client
client = TestClient(app)

print("=== Testing with patch ===")
with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
    mock_list.return_value = [{"test": "data"}]
    
    response = client.get("/api/v1/test")
    print(f"Status: {response.status_code}")
    print(f"Data: {response.json()}")
    print(f"Mock called: {mock_list.called}")
    print(f"Mock call count: {mock_list.call_count}")
