"""Endpoint that triggers a scrape run in the background."""
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException

from src.model.scraper_schema import ExecuteScrapeRequest
from src.service.scraper_service import ScraperService

from ..swagger import docs

router = APIRouter()
scraper_service = ScraperService()

_RULE_FIELDS = ("id", "name", "jsonpath", "css_selector", "xpath", "regex", "output_field", "required")


def _rules_to_dicts(rules):
    if not rules:
        return None
    return [{f: getattr(rule, f) for f in _RULE_FIELDS} for rule in rules]


@router.post(
    "/scrape/execute",
    summary="执行爬虫任务",
    description="根据选择的配置ID在后台执行爬虫任务，立即返回",
)
async def execute_scrape(
    background_tasks: BackgroundTasks,  # injected by FastAPI; do NOT wrap in Depends
    config_request: ExecuteScrapeRequest = Body(..., example=docs.EXECUTE_EXAMPLE),
):
    try:
        background_tasks.add_task(
            scraper_service.execute_scrape,
            config_request.config_id,
            mode=config_request.mode,
            parsing_rules=_rules_to_dicts(config_request.parsing_rules),
        )
        return {
            "success": True,
            "message": f"ID 为 {config_request.config_id} 的爬蟲任務已在背景啟動，請稍後查看資料庫與日誌。",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
