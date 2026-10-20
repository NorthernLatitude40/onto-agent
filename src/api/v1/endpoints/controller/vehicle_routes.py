"""Read-only endpoint for stored vehicle data."""
from typing import List

from fastapi import APIRouter, HTTPException, status

from ..swagger import docs
from ..dao import vehicle_repo
from ..dto.schemas import ScrapedVehicle

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
