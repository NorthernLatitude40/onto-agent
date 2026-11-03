"""
Vehicle Scraper Execution API Endpoint
Handles execution of scraping tasks and retrieval of scraped data
"""
from fastapi import APIRouter, HTTPException, status, Body, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None  # No-op if dotenv not available
from typing import List, Optional
import psycopg2
from decimal import Decimal

load_dotenv()

# Import service for scrape execution logic
from src.service.scraper_service import ScraperService

try:
    from src.model.scraper_schema import ExecuteScrapeRequest, ScrapeConfig
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

class SourceField(BaseModel):
    """Source field structure for preview"""
    name: str = Field(..., description="Display name of the field")
    key: str = Field(..., description="Full path to the field in JSON")
    type: str = Field(..., description="Data type of the field")
    sample: Optional[str] = Field(None, description="Sample value")

class PreviewStepResponse(BaseModel):
    """Response for step preview"""
    source_fields: List[SourceField] = Field(..., description="Flattened source fields from API response")
    status_code: int = Field(..., description="HTTP status code from the target API")

# ==================== Helper Functions ====================
def flatten_json(data, parent_key='', sep='.'):
    """
    Recursively flatten JSON data into a list of source fields

    Args:
        data: The JSON data to flatten
        parent_key: Parent key for recursion
        sep: Separator between keys

    Returns:
        List[SourceField]: Flattened field information
    """
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, (dict, list)):
                items.extend(flatten_json(v, new_key, sep=sep))
            else:
                # Determine type and create source field
                field_type = "string" if isinstance(v, str) else \
                            "number" if isinstance(v, (int, float)) else \
                            "boolean" if isinstance(v, bool) else \
                            "null" if v is None else "unknown"
                items.append({
                    "name": k,
                    "key": new_key,
                    "type": field_type,
                    "sample": str(v)
                })
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            if isinstance(item, (dict, list)):
                items.extend(flatten_json(item, new_key, sep=sep))
            else:
                field_type = "string" if isinstance(item, str) else \
                            "number" if isinstance(item, (int, float)) else \
                            "boolean" if isinstance(item, bool) else \
                            "null" if item is None else "unknown"
                items.append({
                    "name": f"{parent_key}[{i}]",
                    "key": new_key,
                    "type": field_type,
                    "sample": str(item)
                })
    return items

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
    background_tasks=Depends(get_background_tasks)
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
                    "required": rule.required,
                    "mappings": [{"source_key": m.source_key, "target_field": m.target_field} for m in (rule.mappings or [])]
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

# ==================== Preview Endpoints ====================

@router.post(
    "/scraper/preview-step",
    response_model=PreviewStepResponse,
    status_code=status.HTTP_200_OK,
    summary="预览步骤数据",
    description="根据步骤配置执行爬虫并返回源字段列表，用于前端字段映射预览"
)
async def preview_step_data(
    step_config: ScrapeConfig = Body(
        ...,
        description="步骤配置",
        example={
            "target_url": "https://api.example.com/data",
            "headers": {"User-Agent": "Mozilla/5.0"},
            "timeout": 10
        }
    )
):
    """
    预览步骤数据

    该接口根据提供的步骤配置执行爬虫任务，并返回源字段列表，
    用于前端字段映射预览功能。

    Args:
        step_config: 步骤配置信息

    Returns:
        PreviewStepResponse: 包含源字段的响应
    """
    try:
        # Use the scraper service to get real API response
        api_response = await scraper_service._scrape_with_scrapling(
            url=step_config.target_url,
            headers=step_config.headers or {},
            timeout=step_config.timeout
        )

        # Flatten the JSON response into source fields
        if isinstance(api_response, dict):
            source_fields = flatten_json(api_response)
        elif isinstance(api_response, list):
            source_fields = flatten_json({"data": api_response})  # Wrap array in object
        else:
            # For non-JSON responses, create a simple field
            source_fields = [{
                "name": "response",
                "key": "response",
                "type": "string",
                "sample": str(api_response)
            }]

        return {
            "source_fields": source_fields,
            "status_code": 200
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"预览失败: {str(e)}"
        )

