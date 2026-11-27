"""Endpoint that triggers a scrape run in the background."""
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException

from src.model.scraper_schema import ExecuteScrapeRequest
from src.service.scraper_service import ScraperService
from src.api.v1.endpoints.dao import config_repo

from ..swagger import docs

router = APIRouter()
scraper_service = ScraperService()

_RULE_FIELDS = ("id", "name", "jsonpath", "css_selector", "xpath", "regex", "output_field", "required")


def _rules_to_dicts(rules):
    if not rules:
        return None
    return [{f: getattr(rule, f) for f in _RULE_FIELDS} for rule in rules]


import inspect
import logging

logger = logging.getLogger(__name__)


async def _run_and_record(run_id: int, config_id: int, **kwargs):
    try:
        logger.info(f"[执行爬虫] 开始 run_id={run_id}, config_id={config_id}")
        result = await scraper_service.execute_scrape(
            config_id=config_id,
            run_id=run_id,
            **kwargs
        )
        if inspect.isawaitable(result):
            result = await result
        # Extract items_count based on result type
        if isinstance(result, dict):
            # Try to get count from dict first
            count_val = result.get("count")
            if isinstance(count_val, (int, float)) and not isinstance(count_val, bool):
                items_count = int(count_val)
            elif "vehicles" in result:
                vehicles = result.get("vehicles")
                if isinstance(vehicles, (list, tuple)):
                    items_count = len(vehicles)
                else:
                    items_count = 0
            else:
                items_count = 0
        elif isinstance(result, (list, tuple)):
            items_count = len(result)
        else:
            items_count = 0
        logger.info(f"[执行爬虫] 完成 run_id={run_id}, config_id={config_id}, 项数: {items_count}")
        # Log parsing results preview
        if isinstance(result, dict):
            vehicles = result.get("vehicles")
            if isinstance(vehicles, list) and len(vehicles) > 0:
                preview = vehicles[:3] if len(vehicles) > 3 else vehicles
                logger.info(f"[解析结果] run_id={run_id}: {preview}")
        elif isinstance(result, (list, tuple)) and len(result) > 0:
            preview = result[:3] if len(result) > 3 else result
            logger.info(f"[解析结果] run_id={run_id}: {preview}")
        config_repo.finish_run(run_id, success=True, items_count=items_count)
    except Exception as e:
        logger.exception(f"[执行爬虫] 失败 run_id={run_id}, config_id={config_id}: {e}", exc_info=True)
        config_repo.finish_run(run_id, success=False, error=str(e))

@router.post(
    "/scrape/execute",
    summary="执行爬虫任务",
    description="根据选择的配置ID在后台执行爬虫任务，立即返回",
)
async def execute_scrape(
    background_tasks: BackgroundTasks,  # injected by FastAPI; do NOT wrap in Depends
    config_request: ExecuteScrapeRequest = Body(..., examples=docs.EXECUTE_EXAMPLE),
):
    try:
        run_id = config_repo.start_run(config_request.config_id)
        background_tasks.add_task(
             _run_and_record,
             run_id,
            config_request.config_id,
            mode=config_request.mode,
            parsing_rules=_rules_to_dicts(config_request.parsing_rules),
        )
        return {
            "success": True,
             "run_id": run_id,
            "message": f"ID 为 {config_request.config_id} 的爬蟲任務已在背景啟動，請稍後查看資料庫與日誌。",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


