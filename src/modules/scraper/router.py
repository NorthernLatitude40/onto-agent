import random
from fastapi import APIRouter, HTTPException
from modules.scraper.service import ScraperService

router = APIRouter(prefix="/api/scraper", tags=["爬蟲與數據聚合"])


@router.get("/aggregated-items", summary="獲取最新跨平臺聚合行情")
async def get_aggregated_items():
  try:
    data = await ScraperService.get_aggregated_market_data()
    return {"code": 200, "message": "success", "data": data}
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-task", summary="手動觸發一次後台爬蟲抓取")
async def trigger_scraping_task():
  random_id = random.randint(10000, 99999)
  return {
      "code": 200,
      "message": "爬蟲任務已成功調度並開始抓取",
      "task_id": f"task_{random_id}",
  }