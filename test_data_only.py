#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test only the data structure test
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from unittest.mock import patch
from debug_test import app
from fastapi.testclient import TestClient

# Create test client
client = TestClient(app)

print("\n=== Testing /api/v1/vehicles/configs data structure ===")

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
    
    print(f"DEBUG: Calling /api/v1/vehicles/configs")
    response = client.get("/api/v1/vehicles/configs")
    print(f"DEBUG: Status code in test: {response.status_code}")
    if response.status_code != 200:
        print(f"DEBUG: Response text: {response.text}")
    else:
        print(f"DEBUG: Response data: {response.json()}")
    
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    
    if len(data) > 0:
        first_item = data[0]
        # 检查是否有预期的字段 - 根据实际响应数据更新
        expected_fields = ["model_name", "berths", "transmission", "specs"]
        for field in expected_fields:
            assert field in first_item, f"Missing field '{field}' in response"
    
    print("✓ 数据结构测试通过")
