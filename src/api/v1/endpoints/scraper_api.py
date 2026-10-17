"""
Vehicle Scraper API Endpoint
Provides RESTful API for frontend to configure and trigger vehicle data scraping
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from typing import List, Optional
import psycopg2
from fastapi import APIRouter, BackgroundTasks, HTTPException

load_dotenv()

# Import service for scrape execution logic
from src.service.scraper_service import ScraperService

DATABASE_URL = os.environ.get("DATABASE_URL")

router = APIRouter()

# ==================== Request/Response Models ====================

class ScrapeConfig(BaseModel):
    """Configuration for vehicle scraping task"""
    config_id: Optional[int] = None  # For selecting from dropdown
    target_url: Optional[str] = None  # Direct URL override
    headers: Optional[dict] = None
    timeout: Optional[int] = 10

class VehicleSpecs(BaseModel):
    """Vehicle specifications structure"""
    solar: bool
    battery: str
    heater: str
    bed: str

class ScrapedVehicle(BaseModel):
    """Structure for a scraped vehicle"""
    model_name: str
    berths: int
    transmission: str
    specs: VehicleSpecs
    price_nzd: float
    pickup_date: Optional[str] = None
    return_date: Optional[str] = None

class ScrapeResponse(BaseModel):
    """Response after successful scraping"""
    success: bool
    count: int
    message: str
    vehicles: List[ScrapedVehicle]

# ==================== API Endpoints ====================

# Import database models and schemas
try:
    from src.model.scraper_config_model import ScraperConfigModel
except ImportError:
    # Model not yet imported, will be available after table creation
    pass
try:
    from src.model.scraper_schema import (
        ScraperConfigResponse,
        ScraperConfigDetailResponse,
        ScraperConfigCreate,
        ScraperConfigUpdate,
        ExecuteScrapeRequest
    )
except ImportError:
    # Schemas not yet imported, will be available after file creation
    pass

# ==================== Configuration Management Endpoints ====================

@router.get(
    "/configs",
    response_model=List[ScraperConfigResponse],
    status_code=status.HTTP_200_OK,
    summary="获取所有爬虫配置",
    description="从数据库中查询所有可用的爬虫配置，供前端下拉列表使用"
)
def get_scraper_configs():
    """
    获取所有爬虫配置
    
    该接口返回所有存储在数据库中的爬虫配置列表，用于前端下拉菜单选择。
    
    Returns:
        List[ScraperConfigResponse]: 爬虫配置列表
    """
    configs = []
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 查询所有活跃的爬虫配置
        cur.execute("""
            SELECT id, name, target_url, is_active, mode, created_at
            FROM scraper_configs
            WHERE is_active = TRUE
            ORDER BY name;
        """)
        
        rows = cur.fetchall()
        for row in rows:
            config_data = {
                "id": row[0],
                "name": row[1],
                "target_url": row[2],
                "is_active": row[3],
                "mode": str(row[4]),
                "created_at": str(row[5]) if row[5] is not None else None
            }
            configs.append(config_data)
        
    except Exception as e:
        print(f"数据库查询出错: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库查询失败: {str(e)}"
        )
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    return configs

@router.post(
    "/configs",
    response_model=ScraperConfigDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新的爬虫配置",
    description="创建并存储一个新的爬虫配置"
)
def create_scraper_config(config_data: ScraperConfigCreate):
    """
    创建新的爬虫配置
    
    该接口接受爬虫配置数据并存储到数据库中。
    
    Args:
        config_data: 爬虫配置数据
        
    Returns:
        ScraperConfigDetailResponse: 创建后的完整配置信息
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Convert headers to JSON string for PostgreSQL
        import json
        headers_json = json.dumps(config_data.headers) if config_data.headers else None
        
        # Insert new configuration
        cur.execute(
            """
            INSERT INTO scraper_configs (name, target_url, headers, timeout, mode)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, name, target_url, headers, timeout, is_active, mode, created_at, updated_at;
            """,
            (
                config_data.name,
                config_data.target_url,
                headers_json,
                config_data.timeout,
                config_data.mode
            )
        )
        
        result = cur.fetchone()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get configuration after insertion"
            )
        
        conn.commit()
        
        # Return the created configuration
        # Parse headers JSON string back to dict (only if it's a string)
        headers_dict = json.loads(result[3]) if result[3] and isinstance(result[3], str) and result[3] != 'null' else result[3]
        config_response = {
            "id": result[0],
            "name": result[1],
            "target_url": result[2],
            "headers": headers_dict,
            "timeout": result[4],
            "is_active": result[5],
            "mode": str(result[6]),
            "created_at": str(result[7]) if result[7] is not None else None,
            "updated_at": str(result[8]) if result[8] is not None else None
        }
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"数据库写入出错: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库操作失败: {str(e)}"
        )
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    return config_response

@router.get(
    "/scrape/configs/{config_id}",
    response_model=ScraperConfigDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="获取指定爬虫配置",
    description="根据ID查询具体的爬虫配置详情"
)
def get_scraper_config(config_id: int):
    """
    获取指定爬虫配置
    
    该接口返回指定ID的爬虫配置完整详情。
    
    Args:
        config_id: 爬虫配置ID
        
    Returns:
        ScraperConfigDetailResponse: 具体爬虫配置详情
    """
    config = None
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Query specific configuration
        cur.execute("""
            SELECT id, name, target_url, headers, timeout, is_active, mode, created_at, updated_at
            FROM scraper_configs
            WHERE id = %s;
        """, (config_id,))
        
        result = cur.fetchone()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"爬虫配置 ID {config_id} 不存在"
            )
        
        # Parse headers JSON string back to dict (only if it's a string)
        import json
        headers_dict = json.loads(result[3]) if result[3] and isinstance(result[3], str) and result[3] != 'null' else result[3]
        
        config = {
            "id": result[0],
            "name": result[1],
            "target_url": result[2],
            "headers": headers_dict,
            "timeout": result[4],
            "is_active": result[5],
            "mode": str(result[6]),
            "created_at": str(result[7]) if result[7] is not None else None,
            "updated_at": str(result[8]) if result[8] is not None else None
        }
        
    except Exception as e:
        print(f"数据库查询出错: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库查询失败: {str(e)}"
        )
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    return config

@router.put(
    "/scrape/configs/{config_id}",
    response_model=ScraperConfigDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="更新爬虫配置",
    description="根据ID更新指定的爬虫配置"
)
def update_scraper_config(config_id: int, config_data: ScraperConfigUpdate):
    """
    更新爬虫配置
    
    该接口根据ID更新指定的爬虫配置。
    
    Args:
        config_id: 爬虫配置ID
        config_data: 要更新的配置数据
        
    Returns:
        ScraperConfigDetailResponse: 更新后的完整配置信息
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        
        if config_data.name is not None:
            updates.append("name = %s")
            params.append(config_data.name)
        if config_data.target_url is not None:
            updates.append("target_url = %s")
            params.append(config_data.target_url)
        if config_data.headers is not None:
            import json
            headers_json = json.dumps(config_data.headers)
            updates.append("headers = %s")
            params.append(headers_json)
        if config_data.timeout is not None:
            updates.append("timeout = %s")
            params.append(config_data.timeout)
        if config_data.is_active is not None:
            updates.append("is_active = %s")
            params.append(config_data.is_active)
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )
        
        # Add config_id to params
        params.append(config_id)
        
        # Execute update
        query = """
            UPDATE scraper_configs
            SET {updates}
            WHERE id = %s
            RETURNING id, name, target_url, headers, timeout, is_active, mode, created_at, updated_at;
        """.format(updates=", ".join(updates))
        
        cur.execute(query, params)
        
        result = cur.fetchone()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"爬虫配置 ID {config_id} 不存在"
            )
        
        conn.commit()
        
        # Return the updated configuration
        # Parse headers JSON string back to dict (only if it's a string)
        import json
        headers_dict = json.loads(result[3]) if result[3] and isinstance(result[3], str) and result[3] != 'null' else result[3]
        
        config_response = {
            "id": result[0],
            "name": result[1],
            "target_url": result[2],
            "headers": headers_dict,
            "timeout": result[4],
            "is_active": result[5],
            "mode": str(result[6]),
            "created_at": str(result[7]) if result[7] is not None else None,
            "updated_at": str(result[8]) if result[8] is not None else None
        }
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"数据库更新出错: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库操作失败: {str(e)}"
        )
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    return config_response

@router.delete(
    "/scrape/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除爬虫配置",
    description="根据ID删除指定的爬虫配置（软删除：设置is_active=false）"
)
def delete_scraper_config(config_id: int):
    """
    删除爬虫配置
    
    该接口根据ID删除指定的爬虫配置，实际执行软删除（设置is_active=false）。
    
    Args:
        config_id: 爬虫配置ID
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Soft delete by setting is_active to false
        cur.execute(
            """
            UPDATE scraper_configs
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = %s
            RETURNING id;
            """,
            (config_id,)
        )
        
        result = cur.fetchone()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"爬虫配置 ID {config_id} 不存在"
            )
        
        conn.commit()
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"数据库删除出错: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库操作失败: {str(e)}"
        )
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# ==================== Scrape Execution Endpoints ====================

# Initialize scraper service
scraper_service = ScraperService()

@router.post(
    "/scrape/execute",
    status_code=status.HTTP_200_OK,
    summary="执行爬虫任务",
    description="根据选择的配置ID执行爬虫任务并返回结果"
)
def execute_scrape(config_request: ExecuteScrapeRequest, background_tasks: BackgroundTasks):
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
            await scraper_service.execute_scrape(config_request.config_id, mode=config_request.mode)
        
        background_tasks.add_task(run_execute_scrape)

        # 立即回傳給前端，前端不會發生 Timeout 斷線
        return {
            "success": True,
            "message": (
                f"ID 為 {config_request.config_id} 的爬蟲任務已在背景啟動，請稍後查看資料庫與日誌。"
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/scrape/vehicles",
    response_model=List[ScrapedVehicle],
    status_code=status.HTTP_200_OK,
    summary="获取已存储的车型数据",
    description="从数据库中查询所有已存储的车型数据"
)
def get_stored_vehicles():
    """
    获取已存储的车型数据
    
    该接口从数据库中查询所有已存储的车型数据，供前端展示和管理。
    
    Returns:
        List[ScrapedVehicle]: 已存储的车型列表
    """
    vehicles = []
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 查询 van_models 和 pricing_inventory 关联数据
        cur.execute("""
            SELECT vm.id, vm.model_name, vm.berths, vm.transmission, vm.specs,
                   pi.pickup_date, pi.return_date, pi.price_nzd
            FROM van_models vm
            LEFT JOIN pricing_inventory pi ON vm.id = pi.model_id
            ORDER BY vm.id;
        """)
        
        rows = cur.fetchall()
        for row in rows:
            # Handle specs - it could be JSON or string
            specs_data = row[4]
            if isinstance(specs_data, dict):
                vehicle_specs = specs_data
            elif isinstance(specs_data, str):
                try:
                    import json
                    vehicle_specs = json.loads(specs_data)
                except:
                    # Fallback to the original format from scrape_vehicles.py
                    vehicle_specs = {
                        "solar": True,
                        "battery": "100Ah",
                        "heater": "Diesel",
                        "bed": "Double bed"
                    }
            else:
                # Default specs if format is unknown
                vehicle_specs = {
                    "solar": False,
                    "battery": "Unknown",
                    "heater": "Unknown",
                    "bed": "Unknown"
                }
            
            # Ensure all required fields are present with correct types
            if not isinstance(vehicle_specs.get("solar"), bool):
                vehicle_specs["solar"] = False
            if "battery" not in vehicle_specs or not isinstance(vehicle_specs["battery"], str):
                vehicle_specs["battery"] = "Unknown"
            if "heater" not in vehicle_specs or not isinstance(vehicle_specs["heater"], str):
                vehicle_specs["heater"] = "Unknown"
            if "bed" not in vehicle_specs or not isinstance(vehicle_specs["bed"], str):
                vehicle_specs["bed"] = "Unknown"
            
            # Map database specs to expected format
            # The database may have different field names, so we need to normalize them
            normalized_specs = {
                "solar": vehicle_specs.get("solar", False),
                "battery": str(vehicle_specs.get("battery", "Unknown")),
                "heater": str(vehicle_specs.get("heater", "Unknown")),
                "bed": str(vehicle_specs.get("bed", "Unknown"))
            }
            
            vehicle_data = {
                "model_name": row[1],
                "berths": row[2],
                "transmission": row[3],
                "specs": normalized_specs,
                "price_nzd": float(row[7]) if row[7] is not None else 0.0,
                "pickup_date": str(row[5]) if row[5] is not None else None,
                "return_date": str(row[6]) if row[6] is not None else None
            }
            vehicles.append(vehicle_data)
        
    except Exception as e:
        print(f"数据库查询出错: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库查询失败: {str(e)}"
        )
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    return vehicles


