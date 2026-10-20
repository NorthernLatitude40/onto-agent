"""Pydantic models local to the scraper API."""
from typing import List, Optional

from pydantic import BaseModel, Field


class ScrapeConfig(BaseModel):
    config_id: Optional[int] = None
    target_url: Optional[str] = None
    headers: Optional[dict] = None
    timeout: Optional[int] = 10


class VehicleSpecs(BaseModel):
    solar: bool = Field(..., example=True)
    battery: str = Field(..., example="Lithium 200Ah")
    heater: str = Field(..., example="Diesel")
    bed: str = Field(..., example="Double")


class ScrapedVehicle(BaseModel):
    model_name: str
    berths: int
    transmission: str
    specs: VehicleSpecs
    price_nzd: float
    pickup_date: Optional[str] = None
    return_date: Optional[str] = None


class ScrapeResponse(BaseModel):
    success: bool
    count: int
    message: str
    vehicles: List[ScrapedVehicle]
