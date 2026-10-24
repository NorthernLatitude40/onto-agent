# -*- coding: utf-8 -*-
"""
测试路由和性能
"""
import time
from fastapi.testclient import TestClient
from src.api.v1.endpoints.scraper_execution_api import router as scraper_router
from unittest.mock import MagicMock, patch


def test_get_configs_performance(client: TestClient):
    """
    测试 /api/v1/vehicles/configs 端点的性能
    这个测试会多次调用接口并记录响应时间
    """
    # 多次调用以观察缓存效果
    response_times = []
    for i in range(5):
        start_time = time.time()
        response = client.get("/api/v1/vehicles/configs")
        elapsed = time.time() - start_time
        response_times.append(elapsed)
        
        # 验证响应成功
        assert response.status_code == 200, f"Request {i+1} failed: {response.text}"
        
        # 第一次请求可能需要建立连接，后续请求应该更快（如果有缓存）
        if i > 0:
            assert response_times[i] < response_times[0], \
                f"Request {i+1} ({response_times[i]:.3f}s) was not faster than first request ({response_times[0]:.3f}s)"
    
    print(f"\n性能测试结果:")
    print(f"  第一次请求: {response_times[0]:.3f}s")
    print(f"  平均响应时间: {sum(response_times)/len(response_times):.3f}s")
    print(f"  最快响应时间: {min(response_times):.3f}s")
    print(f"  最慢响应时间: {max(response_times):.3f}s")


def test_get_configs_data(client: TestClient):
    """
    测试 /api/v1/vehicles/configs 端点返回正确的数据结构
    """
    # Mock the database dependencies to avoid actual DB connection
    with patch('src.api.v1.endpoints.service.project_service.ProjectService') as mock_service_class:
        with patch('src.common.database.SessionLocal') as mock_session_local:
            mock_service = MagicMock()
            mock_service.get_vehicle_configs.return_value = [
                {
                    "model_name": "Toyota Hiace",
                    "berths": 3,
                    "transmission": "Manual",
                    "specs": {
                        "solar": True,
                        "battery": "Lithium 200Ah"
                    },
                    "price_nzd": 150.0
                }
            ]
            mock_service_class.return_value = mock_service
            
            # Mock session to avoid actual DB connection
            mock_session_instance = MagicMock()
            mock_session_local.return_value = mock_session_instance
        
        print(f"DEBUG: Calling /api/v1/vehicles/configs")
        response = client.get("/api/v1/vehicles/configs")
        print(f"DEBUG: Status code in test: {response.status_code}")
        if response.status_code != 200:
            print(f"DEBUG: Response text: {response.text}")
        else:
            print(f"DEBUG: Response data: {response.json()}")
        assert response.status_code == 200
    
    # Clear cache after test to avoid side effects
    from src.api.v1.endpoints.controller.scraper_projects import _get_vehicle_configs_cached
    _get_vehicle_configs_cached.cache_clear()
    
    data = response.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    
    if len(data) > 0:
        first_item = data[0]
        # 检查是否有预期的字段 - 根据实际响应数据更新
        expected_fields = ["model_name", "berths", "transmission", "specs"]
        for field in expected_fields:
            assert field in first_item, f"Missing field '{field}' in response"


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/workspaces/langgraph_workspace')
    from unittest.mock import patch
    
    # Clear cache BEFORE any imports that might trigger it
    import src.api.v1.endpoints.controller.scraper_projects as scraper_module
    scraper_module._get_vehicle_configs_cached.cache_clear()
    
    from debug_test import app
    
    # 创建测试客户端
    client = TestClient(app)
    
    # Mock the config repo to return test data for /api/v1/vehicles/configs endpoint
    with patch('src.api.v1.endpoints.dao.vehicle_repo.list_vehicles') as mock_list:
        mock_list.return_value = [
            {
                "model_name": "Toyota Hiace",
                "berths": 3,
                "transmission": "Manual",
                "specs": {
                    "solar": True,
                    "battery": "Lithium 200Ah"
                },
                "price_nzd": 150.0
            }
        ]
    
    print("\n=== 测试 /api/v1/vehicles/configs 数据结构 ===")
    test_get_configs_data(client)
    print("✓ 数据结构测试通过")
    
    print("\n=== 测试 /api/v1/vehicles/configs 性能 ===")
    test_get_configs_performance(client)
    print("✓ 性能测试通过")
