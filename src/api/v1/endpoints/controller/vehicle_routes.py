"""Read-only endpoint for stored vehicle data."""
from typing import List
import time
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status

from src.common.database import SessionLocal
from ..swagger import docs
from ..dao import vehicle_repo
from ..dto.schemas import ScrapedVehicle
from src.api.v1.endpoints.service.project_service import ProjectService

router = APIRouter()


@router.get(
    "/scrape/vehicles",
    response_model=List[ScrapedVehicle],
    summary="获取已存储的车型数据",
    responses=docs.VEHICLES_RESPONSES,
)
def get_stored_vehicles():
    try:
        return vehicle_repo.list_vehicles()
    except Exception as e:
        print(f"数据库查询出错: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"数据库查询失败: {e}"
        )

# 2. 获取车辆配置数据（性能优化后的端点）
@lru_cache(maxsize=1)
def _get_vehicle_configs_cached():
    """缓存车辆配置数据，5秒后自动失效"""

    # 使用连接池获取数据库会话
    db = SessionLocal()
    try:
        service = ProjectService(db)
        configs = service.get_vehicle_configs()
        return configs, time.time()
    finally:
        db.close()

@router.get("/configs", tags=["车辆配置查询"])
def get_vehicle_configs():
    """
    获取车辆配置数据

    该端点返回所有车辆的配置信息，包括模型名称、床位数量、传动方式等。
    数据会被缓存5秒以提高性能。
    """
    try:
        cached_data, cache_time = _get_vehicle_configs_cached()

        # 检查缓存是否过期（5秒）
        if time.time() - cache_time > 5:
            # 清除旧缓存并重新获取
            _get_vehicle_configs_cached.cache_clear()
            cached_data, cache_time = _get_vehicle_configs_cached()

        return cached_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取车辆配置失败: {str(e)}"
        )
