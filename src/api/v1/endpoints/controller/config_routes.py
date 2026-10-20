"""CRUD endpoints for scraper configs."""
import json
from typing import List

from fastapi import APIRouter, Body, HTTPException, status

from src.model.scraper_schema import (
    ScraperConfigCreate,
    ScraperConfigDetailResponse,
    ScraperConfigResponse,
    ScraperConfigUpdate,
    ScraperStep,
)

from ..swagger import docs
from ..dao import config_repo
from ..db import get_cursor

router = APIRouter()


def _db_error(e: Exception) -> HTTPException:
    print(f"数据库操作出错: {e}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"数据库操作失败: {e}",
    )


def _not_found(config_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"爬虫配置 ID {config_id} 不存在")


@router.get(
    "/configs",
    response_model=List[ScraperConfigResponse],
    summary="获取所有爬虫配置",
    description="从数据库中查询所有可用的爬虫配置，供前端下拉列表使用",
    responses=docs.LIST_CONFIGS_RESPONSES,
)
def get_scraper_configs():
    try:
        return config_repo.list_active()
    except Exception as e:
        raise _db_error(e)


@router.post(
    "/configs",
    response_model=ScraperConfigDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新的爬虫配置",
)
def create_scraper_config(
    config_data: ScraperConfigCreate = Body(..., example=docs.CREATE_CONFIG_EXAMPLE),
):
    try:
        # Create the scraper config
        config = config_repo.create(
            config_data.name, config_data.target_url, config_data.headers,
            config_data.timeout, config_data.mode,
        )
        
        # Create steps if provided
        if config_data.steps:
            config_repo.create_steps(config["id"], config_data.steps)
        
        return config
    except Exception as e:
        raise _db_error(e)


@router.get(
    "/scrape/configs/{config_id}",
    response_model=ScraperConfigDetailResponse,
    summary="获取指定爬虫配置",
    responses=docs.GET_CONFIG_RESPONSES,
)
def get_scraper_config(config_id: int):
    try:
        config = config_repo.get_by_id(config_id)
    except Exception as e:
        raise _db_error(e)
    if config is None:
        raise _not_found(config_id)
    
    # Add steps to the config - convert raw step data to ScraperStep models
    raw_steps = config_repo.get_steps_by_config_id(config_id)
    steps = []
    for step in raw_steps:
        # Convert target_type back to mode field
        step_dict = {
            "id": step["id"],
            "name": step["name"],
            "mode": step.get("target_type", "api"),  # Map target_type to mode
            "target_url": step["target_url"],
        }
        
        # Merge config data into step_dict
        if step.get("config"):
            config_data = step["config"]

            # 如果 config_data 是字串，先將其解析為 Python 字典
            if isinstance(config_data, str):
                try:
                    config_data = json.loads(config_data)
                except json.JSONDecodeError as e:
                    # 處理 JSON 格式錯誤的情況
                    print(f"JSON 解析失敗: {e}")
                    config_data = {}

            # 確保 config_data 現在是字典，然後再進行合併
            if isinstance(config_data, dict):
                for key in ["method", "params", "headers", "delay", "retry_count", "parsing_rules"]:
                    if key in config_data:
                        step_dict[key] = config_data[key]
        
        # Create ScraperStep instance
        steps.append(ScraperStep(**step_dict))
    
    config["steps"] = steps
    return config


@router.put(
    "/scrape/configs/{config_id}",
    response_model=ScraperConfigDetailResponse,
    summary="更新爬虫配置",
)
def update_scraper_config(
    config_id: int,
    config_data: ScraperConfigUpdate = Body(..., example=docs.UPDATE_CONFIG_EXAMPLE),
):
    fields = {
        k: getattr(config_data, k)
        for k in ("name", "target_url", "headers", "timeout", "is_active")
        if getattr(config_data, k) is not None
    }
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields provided for update")
    try:
        config = config_repo.update(config_id, fields)
    except Exception as e:
        raise _db_error(e)
    if config is None:
        raise _not_found(config_id)
    
    # Handle steps update
    if hasattr(config_data, "steps") and config_data.steps is not None:
        # First delete existing steps for this config
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE crawler_steps SET enabled = FALSE WHERE scraper_config_id = %s;",
                (config_id,),
            )
        
        # Then create new steps
        if config_data.steps:
            config_repo.create_steps(config_id, config_data.steps)
    
    return config


@router.delete(
    "/scrape/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除爬虫配置",
    description="软删除：设置 is_active=false",
)
def delete_scraper_config(config_id: int):
    try:
        deleted = config_repo.soft_delete(config_id)
    except Exception as e:
        raise _db_error(e)
    if not deleted:
        raise _not_found(config_id)
