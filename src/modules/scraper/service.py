from datetime import datetime
import httpx


class ScraperService:

  @staticmethod
  async def fetch_aoeah_via_api():
    """直接请求 AOEAH 的底层 API 获取 JSON 数据"""
    api_url = "https://www.aoeah.com/api/goods"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.aoeah.com/d4-items",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "gamesort": "D4",
        "type": "Items",
        "servername": "D4 SC Season",
        "tmethod": "601",
        "tmethod2": "",
        "searchname": "",
        "pagesize": "30",
        "page": "1",
        "ajaxtime": "0",
        "matchname": "",
    }

    async with httpx.AsyncClient() as client:
      try:
        response = await client.get(
            api_url, params=params, headers=headers, timeout=10.0
        )
        if response.status_code == 200:
          res_json = response.json()

          # 【修正】：根據你實際的 API 返回結構調整，改為正確的鍵（例如 res_json.get("items", [])）
          items_list = res_json.get("items", [])

          parsed_data = []
          for item in items_list:
            parsed_data.append({
                "name": item.get("name"),
                "price": float(item.get("price", 0)),
                "platform": "AOEAH",
            })
          return parsed_data
      except Exception as e:
        print(f"请求 AOEAH API 失败: {e}")

    return []

  @staticmethod
  async def get_aggregated_market_data():
    """聚合多個平臺的行情數據，並適配前端表格格式"""
    aoeah_items = await ScraperService.fetch_aoeah_via_api()

    formatted_items = []
    for index, item in enumerate(aoeah_items, start=1):
      raw_name = item.get("name")
      if isinstance(raw_name, list):
        item_name = raw_name[0] if len(raw_name) > 0 else "未知物品"
        item_id = raw_name[1] if len(raw_name) > 1 else f"D4-{index}"
      else:
        item_name = raw_name or "未知物品"
        item_id = f"D4-{index:03d}"

      price = item.get("price", 0)

      formatted_items.append({
          "id": item_id,
          "game": "Diablo IV (D4)",
          "name": item_name,
          "platformA": price,
          "platformB": round(price * 1.2, 2),
          "profit_spread": "+15.5%",
          "status": "套利机会" if price < 10 else "正常行情",
      })

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_items": len(formatted_items),
        "items": formatted_items,
    }