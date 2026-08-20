# src/api/dashboard_api.py
import time
import uuid
import logging
import json
import re
import hashlib
import ast
import jwt
import httpx
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from datetime import datetime, date, time as dt_time, timedelta

from src.common.database import get_db # 获取数据库连接
from src.service.inventory_service import InventoryService
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from src.core.shop_agent.system import ShopAgentSystem
from src.common.dict import ShopRole
from src.model.models import FinancialRecord
from src.model.inventory_model import InventoryModel as Inventory
from src.model.user_model import UserModel
from src.model.shop_model import ShopModel
from src.model.staff_model import StaffModel
from src.model.order_model import OutboundOrderModel as OutboundOrder
from src.model.schema import  CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload
from src.model.partner_model import Partner
from src.model.models import (
    FinancialRecord
)
from src.model.inventory_model import InventoryModel
from src.api.auth_api import get_current_user, create_access_token
from src.common.exceptions import BusinessException
from src.config.config import settings
from src.dependencies.permissions import allow_shop_manager, allow_shop_staff
from src.model.clark_schema import StaffResponse
from src.model.dashboard_schema import DashboardOverviewResponse
from src.common.i18n import ErrorCode, get_i18n_message
from src.common.redis_client import redis_client
from src.model.inventory_schema import StockListResponse, SellDeviceResponse
from src.common.dict import StockStatusEnum, PaymentStatusEnum

logger = logging.getLogger(__name__)

shop_agent = ShopAgentSystem()

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["首页看板"])

@dashboard_router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="獲取首頁概覽與報表趨勢數據"
)
def get_dashboard_overview(
    range_type: str = Query(
        "today",
        alias="range",
        description="統計時間維度: today (24小時按時段/今日), 7days (近7天按日), month (近6個月按月)"
    ),
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="當前選擇的店鋪ID"),
    db: Session = Depends(get_db),
    current_staff = Depends(allow_shop_manager)
):
    target_shop_id = shop_id or getattr(current_staff, "shop_id", 1)

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 1. 確定時間範圍與分組時間格式 (Date Format)
    if range_type == "7days":
        start_time = today_start - timedelta(days=6)
        end_time = today_end
        date_keys = [(start_time + timedelta(days=i)).strftime("%m-%d") for i in range(7)]
        date_group_expr = func.to_char(FinancialRecord.record_time, 'MM-DD')

    elif range_type == "month":
        start_month = (now.month - 5) if now.month > 5 else (now.month + 7)
        start_year = now.year if now.month > 5 else (now.year - 1)
        start_time = datetime(start_year, start_month, 1, 0, 0, 0)
        end_time = today_end

        date_keys = []
        curr = start_time
        while curr <= now:
            date_keys.append(curr.strftime("%Y-%m"))
            next_month = curr.month % 12 + 1
            next_year = curr.year + (1 if next_month == 1 else 0)
            curr = datetime(next_year, next_month, 1)

        date_group_expr = func.to_char(FinancialRecord.record_time, 'YYYY-MM')

    else:
        # range_type == "today" (默認今日)
        start_time = today_start
        end_time = today_end
        date_keys = [f"{i:02d}:00" for i in range(24)]
        date_group_expr = func.to_char(FinancialRecord.record_time, 'HH24:00')

    # 2. 查詢【在庫設備總數】
    in_stock_count = db.query(
        func.coalesce(func.sum(Inventory.stock_quantity), 0)
    ).filter(
        Inventory.shop_id == target_shop_id,
        Inventory.status == StockStatusEnum.IN_STOCK.value
    ).scalar() or 0

    # 3. 總體統計指標 (修復 profit 計算：取消 case 限制，直接 SUM 全量 profit 欄位)
    total_stats = db.query(
        func.coalesce(func.sum(case((FinancialRecord.type == 1, FinancialRecord.amount), else_=0.0)), 0.0).label("income"),
        func.coalesce(func.sum(case((FinancialRecord.type == 2, FinancialRecord.amount), else_=0.0)), 0.0).label("expense"),
        func.coalesce(func.sum(FinancialRecord.profit), 0.0).label("profit")
    ).filter(
        FinancialRecord.shop_id == target_shop_id,
        FinancialRecord.record_time >= start_time,
        FinancialRecord.record_time <= end_time
    ).first()

    income = float(total_stats.income or 0.0)
    expense = float(total_stats.expense or 0.0)
    profit = float(total_stats.profit or 0.0)

    # 4. 查詢該時間段內的成交單數
    order_count = db.query(
        func.count(OutboundOrder.id)
    ).filter(
        OutboundOrder.shop_id == target_shop_id,
        OutboundOrder.payment_status == PaymentStatusEnum.PAYED.value,
        OutboundOrder.created_at >= start_time,
        OutboundOrder.created_at <= end_time
    ).scalar() or 0

    # 5. 趨勢圖表分組 SQL 查詢 (同樣直接 SUM 全量 profit 欄位)
    trend_query = db.query(
        date_group_expr.label("date_group"),
        func.coalesce(func.sum(case((FinancialRecord.type == 1, FinancialRecord.amount), else_=0.0)), 0.0).label("income"),
        func.coalesce(func.sum(case((FinancialRecord.type == 2, FinancialRecord.amount), else_=0.0)), 0.0).label("expense"),
        func.coalesce(func.sum(FinancialRecord.profit), 0.0).label("profit")
    ).filter(
        FinancialRecord.shop_id == target_shop_id,
        FinancialRecord.record_time >= start_time,
        FinancialRecord.record_time <= end_time
    ).group_by(
        date_group_expr
    ).all()

    # 將數據庫查詢結果轉為字典映射
    db_trend_map: Dict[str, dict] = {}
    for row in trend_query:
        group_key = str(row.date_group)
        db_trend_map[group_key] = {
            "income": round(float(row.income), 2),
            "expense": round(float(row.expense), 2),
            "profit": round(float(row.profit), 2)
        }

    # 6. 內存補齊缺失日期 (補零操作)
    trend_list: List[Dict] = []
    for key in date_keys:
        data = db_trend_map.get(key, {"income": 0.0, "expense": 0.0, "profit": 0.0})
        trend_list.append({
            "date": key,
            "income": data["income"],
            "expense": data["expense"],
            "profit": data["profit"]
        })

    # 7. 返回組裝完成的數據
    return {
        "profit": round(profit, 2),
        "income": round(income, 2),
        "expense": round(expense, 2),
        "order_count": int(order_count),
        "in_stock_devices": int(in_stock_count),
        "trend": trend_list,
        "today_profit": round(profit, 2) if range_type == "today" else 0.0,
        "today_income": round(income, 2) if range_type == "today" else 0.0,
        "today_expense": round(expense, 2) if range_type == "today" else 0.0,
    }

@dashboard_router.get("/search/global")
def global_search(
    q: str = Query(..., min_length=1, description="搜索关键字"),
    x_shop_id: Optional[str] = Header(None, alias="X-Shop-Id"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    if not x_shop_id:
        raise HTTPException(status_code=400, detail="缺少店铺 ID (X-Shop-Id)")

    keyword = f"%{q.strip()}%"

    # 1. 检索在库设备（精准匹配你的 InventoryModel 字段：sn_code, title, spec, remark）
    stocks_query = db.query(InventoryModel).filter(
        InventoryModel.shop_id == x_shop_id,
        or_(
            InventoryModel.sn_code.ilike(keyword),
            InventoryModel.title.ilike(keyword),
            InventoryModel.spec.ilike(keyword),
            InventoryModel.remark.ilike(keyword)
        )
    ).limit(20).all()

    stocks_res = [
        {
            "id": str(stock.id),
            "brand": "",                  # 你的模型里没有 brand，传空或合并到 title
            "model_name": stock.title,    # 对应你的 title 字段
            "imei": stock.sn_code,        # 对应你的 sn_code 串号
            "status": "在库" if stock.status == 1 else "已售",
            "cost_price": float(stock.purchase_price or 0), # 对应 purchase_price
            "price": float(stock.selling_price or 0),       # 对应 selling_price
            "created_at": stock.created_at.strftime("%Y-%m-%d %H:%M") if stock.created_at else ""
        }
        for stock in stocks_query
    ]

    # 2. 检索订单（匹配订单号、客户姓名、客户手机号）
    orders_query = db.query(OutboundOrder).outerjoin(Partner).filter(
        OutboundOrder.shop_id == x_shop_id,
        or_(
            OutboundOrder.order_sn.ilike(keyword),
            Partner.name.ilike(keyword),
            Partner.phone.ilike(keyword)
        )
    ).limit(20).all()

    orders_res = [
        {
            "id": str(order.id),
            "order_no": order.order_no,
            "status": order.status,  # 如: 'completed', 'pending'
            "customer_name": order.customer.name if order.customer else "散客",
            "phone": order.customer.phone if order.customer else "",
            "total_amount": float(order.total_amount or 0),
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M") if order.created_at else ""
        }
        for order in orders_query
    ]

    # 3. 返回整合结果
    return {
        "code": 200,
        "message": "success",
        "data": {
            "stocks": stocks_res,
            "orders": orders_res
        }
    }




shop_router = APIRouter(prefix="/api/v1/shop", tags=["店铺业务"])



# ──────── 业务 B 接口 (手机店小程序) ────────
# 1. 定義標準的請求載荷（Payload）
class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None  # 允許外部傳入自訂的會話 ID，用於辨識不同用戶

@shop_router.post("/chat")
async def shop_chat(
    req: ChatPayload,
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    x_user_role: Optional[str] = Header("staff", alias="X-User-Role"),
):
  if not x_shop_id:
    raise HTTPException(status_code=400, detail="请求头缺少 X-Shop-Id")

  config = {
      "configurable": {
          "thread_id": req.session_id or "default_session",
          "shop_id": x_shop_id,
          "role": x_user_role,
      }
  }

  # 执行 Agent
  result = await shop_agent.graph.ainvoke(
      {"messages": [("user", req.message)]}, config
  )
  messages = result["messages"]
  last_msg = messages[-1]

  raw_content = last_msg.content or ""

  # ---------------------------------------------------------
  # 辅助函数：递归提取 JSON 对象（解决多重转义/套娃字符串）
  # ---------------------------------------------------------
  def extract_json_from_str(text_or_obj):
    """把各种格式（包括 list、带 ```json 的字符串、嵌套 JSON 字符串）强行转为 dict"""
    if isinstance(text_or_obj, dict):
      return text_or_obj

    if isinstance(text_or_obj, list):
      combined_text = ""
      for item in text_or_obj:
        if isinstance(item, dict):
          combined_text += item.get("text", "")
        else:
          combined_text += str(item)
      return extract_json_from_str(combined_text)

    if isinstance(text_or_obj, str):
      clean_str = text_or_obj.strip()
      # 贪婪匹配 JSON 结构
      json_match = re.search(
          r"```json\s*(\{.*\})\s*```", clean_str, re.DOTALL
      ) or re.search(r"(\{.*\})", clean_str, re.DOTALL)
      if json_match:
        try:
          return json.loads(json_match.group(1))
        except Exception:
          pass
    return None

  # ---------------------------------------------------------
  # 🌟 步骤 1：【第一优先级】优先解包 LLM 产生的内层 JSON 结构！
  # ---------------------------------------------------------
  reply_text = ""
  parsed_data = None

  llm_json = extract_json_from_str(raw_content)

  if isinstance(llm_json, dict) and "reply" in llm_json:
    # 拿到外层的 reply
    reply_text = llm_json.get("reply", "")
    parsed_data = llm_json.get("parsedData", None)

    # 🌟 关键点：如果内层 reply 依然是个 JSON 字符串，再解一次包！
    inner_json = extract_json_from_str(reply_text)
    if isinstance(inner_json, dict) and "reply" in inner_json:
      reply_text = inner_json.get("reply", "")
      # 如果内层解析出了更好的 parsedData (如 urn:error)，覆盖它
      if inner_json.get("parsedData"):
        parsed_data = inner_json.get("parsedData")

  # ---------------------------------------------------------
  # 🌟 步骤 2：【第二优先级】如果 LLM 没提供 parsedData，再去拿 ToolMessage
  # ---------------------------------------------------------
  if not parsed_data:
    for msg in reversed(messages):
      if (
          getattr(msg, "type", None) == "user"
          or msg.__class__.__name__ == "HumanMessage"
      ):
        break

      if (
          getattr(msg, "type", None) == "tool"
          or msg.__class__.__name__ == "ToolMessage"
      ):
        content = getattr(msg, "content", None)
        if isinstance(content, dict):
          parsed_data = content
        elif isinstance(content, str) and content.strip():
          try:
            parsed_data = json.loads(content)
          except Exception:
            try:
              parsed_data = ast.literal_eval(content)
            except Exception:
              pass
        if parsed_data:
          break

  # 如果 reply_text 没拿到，兜底为 raw_content
  if not reply_text:
    reply_text = (
        raw_content if isinstance(raw_content, str) else str(raw_content)
    )

  # ---------------------------------------------------------
  # 🌟 步骤 3：【防御拦截】消除非法卡片 (设备ID为空的情况)
  # ---------------------------------------------------------
  if parsed_data and isinstance(parsed_data, dict):
    # 如果 action 是 sell 且 device_id 为 None，说明大模型在没有指定设备 ID 的情况下盲目发了卡片
    if (
        parsed_data.get("action") == "sell"
        and parsed_data.get("device_id") is None
    ):
      # 1. 扔掉这个无意义的 parsedData，防止前端渲染出无法出库的卡片
      parsed_data = None
      # 2. 如果提示语不够明确，提示用户补全 ID
      if "请提供" not in reply_text and "哪一台" not in reply_text:
        reply_text += " （请补充具体要出售的设备 ID）"

  # ---------------------------------------------------------
  # 4. 返回给前端
  # ---------------------------------------------------------
  return {"reply": reply_text, "parsedData": parsed_data}



