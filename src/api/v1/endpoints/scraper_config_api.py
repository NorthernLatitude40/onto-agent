"""
Vehicle Scraper Configuration API Endpoint
Manages scraper configurations (CRUD operations)
"""
from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
from typing import List, Optional
import psycopg2

load_dotenv()

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
        ScraperConfigUpdate
    )
except ImportError:
    # Schemas not yet imported, will be available after file creation
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")

router = APIRouter()

# ==================== Request/Response Models ====================

class ScrapeConfig(BaseModel):
    """Configuration for vehicle scraping task"""
    config_id: Optional[int] = None  # For selecting from dropdown
    target_url: Optional[str] = None  # Direct URL override
    headers: Optional[dict] = None
    timeout: Optional[int] = 10

# ==================== Configuration Management Endpoints ====================

@router.get(
    "/configs",
    response_model=List[ScraperConfigResponse],
    status_code=status.HTTP_200_OK,
    summary="获取所有爬虫配置",
    description="从数据库中查询所有可用的爬虫配置，供前端下拉列表使用",
    responses={
        200: {
            "description": "成功返回爬虫配置列表",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "name": "GetLost NZ Campervan Scraper",
                            "target_url": "https://getlostinnz.co.nz/",
                            "is_active": True,
                            "mode": "api",
                            "created_at": "2024-01-15T10:30:00.000Z"
                        },
                        {
                            "id": 2,
                            "name": "Spaceships Campervans Scraper",
                            "target_url": "https://spaceships.co.nz/",
                            "is_active": True,
                            "mode": "html",
                            "created_at": "2024-01-16T14:20:00.000Z"
                        }
                    ]
                }
            }
        },
        500: {
            "description": "数据库查询失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "数据库查询失败: connection error"
                    }
                }
            }
        }
    }
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
def create_scraper_config(config_data: ScraperConfigCreate= Body(
        ...,
        description="爬虫配置資料",
        example={
            "name": "範例爬蟲任務",
            "target_url": "http://localhost:5173/scraper-config",
            "headers": {"User-Agent": "Mozilla/5.0"},
            "timeout": 10,
            "mode": "api",
            "steps": [
                {
                    "name": "初始請求",
                    "mode": "api",
                    "url": "http://localhost:5173/scraper-config",
                    "method": "GET",
                    "params_json": "{}",
                    "headers_json": "{}",
                    "parsing_rules": [],
                }
            ],
        },
    )):
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
        
        config_id = result[0]
        
        # Save steps to crawler_steps table if provided
        if config_data.steps:
            for step in config_data.steps:
                # Convert parsing_rules to JSON string
                parsing_rules_json = json.dumps([rule.model_dump() for rule in step.parsing_rules]) if step.parsing_rules else "[]"
                
                # Insert step configuration
                cur.execute(
                    """
                    INSERT INTO crawler_steps (scraper_config_id, name, target_type, target_url, config)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        config_id,
                        step.name,
                        step.mode,
                        step.url,
                        json.dumps({
                            "method": step.method,
                            "params_json": step.params_json,
                            "headers_json": step.headers_json,
                            "parsing_rules": parsing_rules_json,
                            "delay": step.delay,
                            "retry_count": step.retry_count
                        })
                    )
                )
        
        conn.commit()
        
        # Fetch steps for the response
        steps = []
        if config_data.steps:
            cur.execute("""
                SELECT id, name, target_type, target_url, config
                FROM crawler_steps
                WHERE scraper_config_id = %s
                ORDER BY id;
            """, (config_id,))
            
            step_rows = cur.fetchall()
            for step_row in step_rows:
                step_config = json.loads(step_row[4]) if step_row[4] else {}
                steps.append({
                    "id": str(step_row[0]),
                    "name": step_row[1],
                    "mode": step_row[2],
                    "url": step_row[3],
                    "method": step_config.get("method", "GET"),
                    "params_json": step_config.get("params_json"),
                    "headers_json": step_config.get("headers_json"),
                    "parsing_rules": json.loads(step_config.get("parsing_rules", "[]")) if step_config.get("parsing_rules") else [],
                    "delay": step_config.get("delay"),
                    "retry_count": step_config.get("retry_count")
                })
        
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
            "steps": steps if config_data.steps else None,
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
    description="根据ID查询具体的爬虫配置详情",
    responses={
        200: {
            "description": "成功返回爬虫配置详情",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "GetLost NZ Campervan Scraper",
                        "target_url": "https://getlostinnz.co.nz/",
                        "headers": {
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "application/json"
                        },
                        "timeout": 10,
                        "is_active": True,
                        "mode": "api",
                        "steps": [
                            {
                                "id": "step-1",
                                "name": "获取车型列表",
                                "mode": "api",
                                "url": "https://getlostinnz.co.nz/wp-json/getlost/v1/rcm/step2",
                                "method": "POST",
                                "params_json": "{\"pickupdate\": \"2026-11-10\"}",
                                "headers_json": "{\"Content-Type\": \"application/json\"}",
                                "parsing_rules": [
                                    {
                                        "id": "rule-1",
                                        "name": "解析车型列表",
                                        "jsonpath": "$.cars[*].vehiclecategory",
                                        "output_field": "model_name",
                                        "required": True
                                    }
                                ],
                                "delay": 1000,
                                "retry_count": 3
                            }
                        ],
                        "created_at": "2024-01-15T10:30:00.000Z",
                        "updated_at": "2024-01-16T14:20:00.000Z"
                    }
                }
            }
        },
        404: {
            "description": "爬虫配置不存在",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "爬虫配置 ID 123 不存在"
                    }
                }
            }
        },
        500: {
            "description": "数据库查询失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "数据库查询失败: connection error"
                    }
                }
            }
        }
    }
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
        
        # Fetch steps for the response
        cur.execute("""
            SELECT id, name, target_type, target_url, config
            FROM crawler_steps
            WHERE scraper_config_id = %s
            ORDER BY id;
        """, (config_id,))
        
        step_rows = cur.fetchall()
        steps = []
        for step_row in step_rows:
            step_config = json.loads(step_row[4]) if step_row[4] else {}
            steps.append({
                "id": str(step_row[0]),
                "name": step_row[1],
                "mode": step_row[2],
                "url": step_row[3],
                "method": step_config.get("method", "GET"),
                "params_json": step_config.get("params_json"),
                "headers_json": step_config.get("headers_json"),
                "parsing_rules": json.loads(step_config.get("parsing_rules", "[]")) if step_config.get("parsing_rules") else [],
                "delay": step_config.get("delay"),
                "retry_count": step_config.get("retry_count")
            })
        
        config = {
            "id": result[0],
            "name": result[1],
            "target_url": result[2],
            "headers": headers_dict,
            "timeout": result[4],
            "is_active": result[5],
            "mode": str(result[6]),
            "steps": steps if steps else None,
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
def update_scraper_config(
    config_id: int,
    config_data: ScraperConfigUpdate = Body(
        ...,
        description="要更新的爬虫配置数据",
        example={
            "name": "Updated Campervan Scraper",
            "target_url": "https://updated-url.com/",
            "headers": {"User-Agent": "Mozilla/5.0"},
            "timeout": 20,
            "is_active": True
        }
    )
):
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
        
        # Handle steps update
        if config_data.steps is not None:
            # First, delete existing steps for this config
            cur.execute("""
                DELETE FROM crawler_steps
                WHERE scraper_config_id = %s;
            """, (config_id,))
            
            # Then insert new steps
            if config_data.steps:
                for step in config_data.steps:
                    parsing_rules_json = json.dumps([rule.model_dump() for rule in step.parsing_rules]) if step.parsing_rules else "[]"
                    cur.execute(
                        """
                        INSERT INTO crawler_steps (scraper_config_id, name, target_type, target_url, config)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (
                            config_id,
                            step.name,
                            step.mode,
                            step.url,
                            json.dumps({
                                "method": step.method,
                                "params_json": step.params_json,
                                "headers_json": step.headers_json,
                                "parsing_rules": parsing_rules_json,
                                "delay": step.delay,
                                "retry_count": step.retry_count
                            })
                        )
                    )
        
        conn.commit()
        
        # Return the updated configuration
        # Parse headers JSON string back to dict (only if it's a string)
        import json
        headers_dict = json.loads(result[3]) if result[3] and isinstance(result[3], str) and result[3] != 'null' else result[3]
        
        # Fetch steps for the response
        cur.execute("""
            SELECT id, name, target_type, target_url, config
            FROM crawler_steps
            WHERE scraper_config_id = %s
            ORDER BY id;
        """, (config_id,))
        
        step_rows = cur.fetchall()
        steps = []
        for step_row in step_rows:
            step_config = json.loads(step_row[4]) if step_row[4] else {}
            steps.append({
                "id": str(step_row[0]),
                "name": step_row[1],
                "mode": step_row[2],
                "url": step_row[3],
                "method": step_config.get("method", "GET"),
                "params_json": step_config.get("params_json"),
                "headers_json": step_config.get("headers_json"),
                "parsing_rules": json.loads(step_config.get("parsing_rules", "[]")) if step_config.get("parsing_rules") else [],
                "delay": step_config.get("delay"),
                "retry_count": step_config.get("retry_count")
            })
        
        config_response = {
            "id": result[0],
            "name": result[1],
            "target_url": result[2],
            "headers": headers_dict,
            "timeout": result[4],
            "is_active": result[5],
            "mode": str(result[6]),
            "steps": steps if config_data.steps is not None else None,
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
