"""
Vehicle Scraper Execution API Endpoint
Handles execution of scraping tasks and retrieval of scraped data
"""
from fastapi import APIRouter, HTTPException, status, Body, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
from typing import List, Optional
import psycopg2
from decimal import Decimal

load_dotenv()

# Import service for scrape execution logic
from src.service.scraper_service import ScraperService

try:
    from src.model.scraper_schema import ExecuteScrapeRequest
except ImportError:
    # Schemas not yet imported, will be available after file creation
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")

router = APIRouter()

# Background tasks dependency
def get_background_tasks() -> BackgroundTasks:
    """Dependency to provide background tasks"""
    return BackgroundTasks()

# ==================== Request/Response Models ====================

class VehicleSpecs(BaseModel):
    """Vehicle specifications structure"""
    solar: bool = Field(..., example=True)
    battery: str = Field(..., example="Lithium 200Ah")
    heater: str = Field(..., example="Diesel")
    bed: str = Field(..., example="Double")

class ScrapedVehicle(BaseModel):
    """Structure for a scraped vehicle"""
    model_name: str
    berths: int
    transmission: str
    specs: VehicleSpecs
    price_nzd: Decimal
    pickup_date: Optional[str] = None
    return_date: Optional[str] = None

class ScrapeResponse(BaseModel):
    """Response after successful scraping"""
    success: bool
    count: int
    message: str
    vehicles: List[ScrapedVehicle]

# ==================== Scrape Execution Endpoints ====================

# Initialize scraper service
scraper_service = ScraperService()

@router.post(
    "/scrape/execute",
    status_code=status.HTTP_200_OK,
    summary="执行爬虫任务",
    description="根据选择的配置ID执行爬虫任务并返回结果"
)
async def execute_scrape(
    config_request: ExecuteScrapeRequest = Body(
        ...,
        description="爬虫任务请求参数",
        example={
            "config_id": 1,
            "pickup_date": "2026-11-10",
            "return_date": "2026-11-15"
        }
    ),
    *,  # Make all following parameters keyword-only
    background_tasks: BackgroundTasks = Depends(get_background_tasks)
):
    """
    执行爬虫任务
    
    该接口根据选择的配置ID从数据库加载配置，然后执行爬虫任务。
    
    Args:
        config_request: 包含config_id的请求体
        
    Returns:
        ScrapeResponse: 爬虫任务结果
    """
    try:
        # Use asyncio.run to execute the async function in the background task
        import asyncio
        
        async def run_execute_scrape():
            # Convert ParsingRule objects to dicts for the service
            parsing_rules_dict = [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "jsonpath": rule.jsonpath,
                    "css_selector": rule.css_selector,
                    "xpath": rule.xpath,
                    "regex": rule.regex,
                    "output_field": rule.output_field,
                    "required": rule.required
                }
                for rule in config_request.parsing_rules
            ] if config_request.parsing_rules else None
            
            await scraper_service.execute_scrape(
                config_request.config_id,
                mode=config_request.mode,
                parsing_rules=parsing_rules_dict
            )
        
        background_tasks.add_task(run_execute_scrape)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # 立即回傳給前端，前端不會發生 Timeout 斷線
    return {
        "success": True,
        "message": (
            f"ID 為 {config_request.config_id} 的爬蟲任務已在背景啟動，請稍後查看資料庫與日誌。"
        ),
    }

