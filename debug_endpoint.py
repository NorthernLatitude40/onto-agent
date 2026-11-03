#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug script to test the /api/v1/vehicles/configs endpoint directly
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from unittest.mock import patch
from debug_test import app
from fastapi.testclient import TestClient

# Create test client
client = TestClient(app)

# Mock the config repo to return test data
with patch('src.api.v1.endpoints.dao.config_repo.list_active') as mock_list:
    mock_list.return_value = [
        {
            "id": 1,
            "name": "GetLost NZ Campervans",
            "target_url": "https://getlostinnz.co.nz/",
            "headers": {"User-Agent": "Test Agent"},
            "timeout": 15,
            "is_active": True,
            "mode": "api"
        }
    ]
    
    print("Testing /api/v1/vehicles/configs endpoint...")
    response = client.get("/api/v1/vehicles/configs")
    
    print(f"Status code: {response.status_code}")
    print(f"Response type: {type(response)}")
    
    if hasattr(response, 'text'):
        print(f"Response text: {response.text[:500]}")
    elif hasattr(response, 'content'):
        print(f"Response content: {response.content[:500]}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"JSON data: {data}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
    else:
        print(f"Request failed with status {response.status_code}")
