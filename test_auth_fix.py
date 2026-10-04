#!/usr/bin/env python3
"""
Test script to verify authentication API fixes
"""

import asyncio
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

# Import the FastAPI app and router
from src.api.v1.endpoints.auth_api import router as auth_router
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

app = FastAPI()
app.include_router(auth_router, prefix="/auth")

async def test_auth_endpoints():
    """Test authentication endpoints with proper dependency injection"""
    
    print("Testing authentication endpoints...")
    
    # Create a mock user object (simplified)
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "test_user"
    mock_user.email = "user@example.com"
    mock_user.phone = "1234567890"
    mock_user.role = "staff"
    
    # Test GET /auth/me endpoint
    print("\n1. Testing GET /auth/me endpoint...")
    with patch('src.api.v1.endpoints.auth_api.get_current_user_from_token') as mock_dep:
        mock_dep.return_value = mock_user
        
        client = TestClient(app)
        response = client.get("/auth/me")
        
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            assert data['id'] == 1
            assert data['username'] == "test_user"
            assert data['email'] == "user@example.com"
            assert data['phone'] == "1234567890"
            assert data['role'] == "staff"
            print("   ✓ GET /auth/me works correctly!")
        else:
            print(f"   ✗ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    
    # Test PUT /auth/me endpoint
    print("\n2. Testing PUT /auth/me endpoint...")
    with patch('src.api.v1.endpoints.auth_api.get_current_user_from_token') as mock_dep:
        mock_dep.return_value = mock_user
        
        client = TestClient(app)
        response = client.put("/auth/me")
        
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            assert data['code'] == 200
            assert "successfully" in data['message'].lower()
            print("   ✓ PUT /auth/me works correctly!")
        else:
            print(f"   ✗ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    
    # Test POST /auth/wx-login endpoint
    print("\n3. Testing POST /auth/wx-login endpoint...")
    mock_db = MagicMock(spec=Session)
    
    with patch('src.api.v1.endpoints.auth_api.get_db') as mock_db_dep:
        mock_db_dep.return_value = mock_db
        
        client = TestClient(app)
        response = client.post("/auth/wx-login", json={"code": "test_code_123"})
        
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            assert data['code'] == 200
            assert "successful" in data['message'].lower()
            print("   ✓ POST /auth/wx-login works correctly!")
        else:
            print(f"   ✗ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    
    print("\n✅ All authentication endpoint tests passed!")

if __name__ == "__main__":
    asyncio.run(test_auth_endpoints())
