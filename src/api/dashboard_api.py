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
from src.model.order_model import OutboundOrder
from src.model.schema import  CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload
from src.model.partner_model import Partner
from src.model.models import (
    FinancialRecord, 
    OutboundOrderItem
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


logger = logging.getLogger(__name__)

shop_agent = ShopAgentSystem()

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["首页看板"])

@dashboard_router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="获取首页概览与报表趋势数据"
)
def get_dashboard_overview(
    # 使用 alias="range" 确保前端依然传递 ?range=today，但在函数内部使用 range_type 避免覆盖内置 range()
    range_type: str = Query(
        "today",
        alias="range",
        description="统计时间维度: today (24小时按时段/今日), 7days (近7天按日), month (近6个月按月)"
    ),
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: Session = Depends(get_db),
    current_staff = Depends(allow_shop_manager)
):
    target_shop_id = shop_id or getattr(current_staff, "shop_id", 1)

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 1. 确定时间范围与分组时间格式 (Date Format)
    if range_type == "7days":
        start_time = today_start - timedelta(days=6)
        end_time = today_end
        # 生成连续的日期 Key 列表 (用于后续补零)
        date_keys = [(start_time + timedelta(days=i)).strftime("%m-%d") for i in range(7)]
        # SQL 日期格式化表达 (PostgreSQL/MySQL 兼容写法)
        date_group_expr = func.to_char(FinancialRecord.record_time, 'MM-DD')

    elif range_type == "month":
        # 近 6 个月趋势：计算 5 个月前的 1 号
        start_month = (now.month - 5) if now.month > 5 else (now.month + 7)
        start_year = now.year if now.month > 5 else (now.year - 1)
        start_time = datetime(start_year, start_month, 1, 0, 0, 0)
        end_time = today_end

        # 生成近 6 个月月份 Key 列表
        date_keys = []
        curr = start_time
        while curr <= now:
            date_keys.append(curr.strftime("%Y-%m"))
            # 递增一个月
            next_month = curr.month % 12 + 1
            next_year = curr.year + (1 if next_month == 1 else 0)
            curr = datetime(next_year, next_month, 1)

        date_group_expr = func.to_char(FinancialRecord.record_time, 'YYYY-MM')

    else:
        # range_type == "today" (默认今日)
        start_time = today_start
        end_time = today_end
        # 今日 24 小时节点: 00:00, 01:00... 23:00
        date_keys = [f"{i:02d}:00" for i in range(24)]
        date_group_expr = func.to_char(FinancialRecord.record_time, 'HH24:00')

    # 2. 查询【在库设备总数】
    in_stock_count = db.query(
        func.coalesce(func.sum(Inventory.stock_quantity), 0)
    ).filter(
        Inventory.shop_id == target_shop_id,
        Inventory.status == 1
    ).scalar()

    # 3. 总体统计指标 (当前 range_type 汇总)
    total_stats = db.query(
        func.coalesce(func.sum(case((FinancialRecord.type == 1, FinancialRecord.amount), else_=0.0)), 0.0).label("income"),
        func.coalesce(func.sum(case((FinancialRecord.type == 2, FinancialRecord.amount), else_=0.0)), 0.0).label("expense"),
        func.coalesce(func.sum(case((FinancialRecord.type == 1, FinancialRecord.profit), else_=0.0)), 0.0).label("profit")
    ).filter(
        FinancialRecord.shop_id == target_shop_id,
        FinancialRecord.record_time >= start_time,
        FinancialRecord.record_time <= end_time
    ).first()

    income = float(total_stats.income or 0.0)
    expense = float(total_stats.expense or 0.0)
    profit = float(total_stats.profit or 0.0)

    # 4. 查询该时间段内的成交单数
    order_count = db.query(
        func.count(OutboundOrder.id)
    ).filter(
        OutboundOrder.shop_id == target_shop_id,
        OutboundOrder.payment_status == 1,
        OutboundOrder.created_at >= start_time,
        OutboundOrder.created_at <= end_time
    ).scalar() or 0

    # 5. 趋势图表分组 SQL 查询 (Group By Date)
    trend_query = db.query(
        date_group_expr.label("date_group"),
        func.coalesce(func.sum(case((FinancialRecord.type == 1, FinancialRecord.amount), else_=0.0)), 0.0).label("income"),
        func.coalesce(func.sum(case((FinancialRecord.type == 2, FinancialRecord.amount), else_=0.0)), 0.0).label("expense"),
        func.coalesce(func.sum(case((FinancialRecord.type == 1, FinancialRecord.profit), else_=0.0)), 0.0).label("profit")
    ).filter(
        FinancialRecord.shop_id == target_shop_id,
        FinancialRecord.record_time >= start_time,
        FinancialRecord.record_time <= end_time
    ).group_by(
        date_group_expr
    ).all()

    # 将数据库查询结果转为字典格式映射
    db_trend_map: Dict[str, dict] = {}
    for row in trend_query:
        group_key = str(row.date_group)
        db_trend_map[group_key] = {
            "income": round(float(row.income), 2),
            "expense": round(float(row.expense), 2),
            "profit": round(float(row.profit), 2)
        }

    # 6. 内存补齐缺失日期 (补零操作，确保 X 轴连续不移位)
    trend_list: List[Dict] = []
    for key in date_keys:
        data = db_trend_map.get(key, {"income": 0.0, "expense": 0.0, "profit": 0.0})
        trend_list.append({
            "date": key,
            "income": data["income"],
            "expense": data["expense"],
            "profit": data["profit"]
        })

    # 7. 返回组装完成的数据
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

# ------------------------------------------------------------------
# 2. 接口实现：GET /api/v1/shop/inventory/list
# ------------------------------------------------------------------
# 注意：把参数 query 中的 status 改名为 stock_status，避免与 fastapi.status 模块重名冲突！
@shop_router.get("/inventory/list", response_model=StockListResponse)
def get_inventory_list(
    stock_status: Optional[int] = Query(None, alias="status", description="库存状态: 1-在库, 2-已售, 3-退货等"),
    db: Session = Depends(get_db),
    # 🌟 核心重构：直接注入依赖，一行代码搞定身份+店铺+权限校验，并直接返回 StaffModel
    current_staff: StaffModel = Depends(allow_shop_staff) 
):
    """
    获取当前店铺下的设备库存列表（支持按状态筛选）
    """
    # 1. 直接从 current_staff 中安全获取当前请求的 shop_id
    shop_id = current_staff.shop_id

    # 2. 基础查询：过滤当前店铺的数据
    query = db.query(InventoryModel).filter(InventoryModel.shop_id == shop_id)

    # 3. 如果前端传了 status 参数
    if stock_status is not None:
        query = query.filter(InventoryModel.status == stock_status)

    # 4. 按创建时间倒序
    items = query.order_by(InventoryModel.created_at.desc()).all()

    # 遵循 Bare Payload 规范返回
    return {"items": items}






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

class AddDeviceConfirmPayload(BaseModel):
    model: str = Field(..., description="设备型号，如：iPhone 13 128G")
    cost: float = Field(..., description="采购/回收成本价")
    color: Optional[str] = Field(default="未知", description="设备颜色")
    notes: Optional[str] = Field(default="二手回收", description="备注信息")


@shop_router.post("/device/add", summary="确认设备入库落库")
async def confirm_add_device(
    payload: AddDeviceConfirmPayload, 
    db: Session = Depends(get_db),
    # 🌟 提取请求头里的 X-Shop-Id
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id")
):
    """
    前端点击【确认入库】卡片时调用的接口：
    1. 在 inventory 表创建一条在库记录 (status=1)
    2. 在 financial_record 表创建一条支出流水 (type=2)
    """
    # 🌟 校验 shop_id，如果没传或者拿不到直接拦住，避免抛 500 报错
    if not x_shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="缺少必要参数：请求头中未包含 X-Shop-Id"
        )
    
    # 🌟 1. 生成唯一请求签名 (Hash Key)
    # 根据用户设备特征（型号、成本、备注等）计算 MD5 摘要
    raw_str = f"add_{payload.model}_{payload.cost}_{payload.notes}"
    lock_key = f"lock:device_add:{hashlib.md5(raw_str.encode()).hexdigest()}"

    # 🌟 2. 尝试向 Redis 获取锁 (ex=5 表示 5 秒内防重复提交)
    # set(..., nx=True) 表示只有 key 不存在时才能设置成功，成功返回 True，失败返回 None
    is_locked = redis_client.set(lock_key, "locked", ex=5, nx=True)

    if not is_locked:
        # 如果获取锁失败，说明 5 秒内有重复提交
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请勿重复提交！正在处理中..."
        )
    try:
        # 1. 创建设备库存记录
        new_device = InventoryModel(
            title=payload.model,
            purchase_price=payload.cost,
            spec=f"颜色:{payload.color}" if payload.color != "未知" else "规格:标准",
            remark=payload.notes,
            category=2,  # 2 - 二手机
            status=1,     # 1 - 在库
            shop_id=x_shop_id
        )
        db.add(new_device)
        db.flush()  # 提前获取自动生成的 ID，但不提交事务

        # 2. 生成财务支出流水单号与记录
        record_sn = f"EXP_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"
        financial_record = FinancialRecord(
            record_sn=record_sn,
            type=2,                                  # 1-收入，2-支出
            category="二手回收",                      # 科目
            amount=payload.cost,                     # 支出金额
            profit=0.0,                              # 🌟 进货不计入利润/亏损，必须设为 0！
            business_type=1,                         # 关联业务：1-手机设备
            business_id=new_device.id,               # 绑定新增的设备 ID
            payment_method="微信",                    # 默认方式，可根据前端调整
            remark=f"设备回收入库：{payload.model} ({payload.notes or ''})",
            shop_id=x_shop_id
        )
        db.add(financial_record)

        # 3. 统一提交事务
        db.commit()
        db.refresh(new_device)

        return {
            "code": 200,
            "message": "设备成功入库并记账！",
            "data": {
                "id": new_device.id,
                "model": new_device.title,
                "cost": new_device.purchase_price,
                "record_sn": record_sn
            }
        }

    except Exception as e:
        db.rollback()
        redis_client.delete(lock_key)
        logger.exception("【API 错误】设备确认入库失败:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"入库失败: {str(e)}"
        )


# ====================================================
# 2. 确认出售 API (请求体 & 路由接口)
# ====================================================

class SellDeviceConfirmPayload(BaseModel):
    model: str = Field(..., description="设备型号或关键词，如：iPhone 13 128G 或 设备ID")
    price: float = Field(..., description="实际出售价格/成交价")
    payment_method: Optional[str] = Field(default="微信", description="收款方式")
    notes: Optional[str] = Field(default="二手销售", description="备注信息")

import re

# 1. 定义指代词黑名单（正则表达式）
PRONOUN_PATTERN = re.compile(
    r"^(刚才|上|这|那|刚刚|那个|这台|那台|上一台|刚才这台|刚才那台|它|把它)+(机器|手机|设备|产品|东西)?$"
)

def clean_device_model(model_str: str, db_session, shop_id: int) -> str:
    """后端防御：清洗 LLM 传过来的型号，如果是代词则自动查找最近一条库存设备"""
    if not model_str:
        return ""

    # 去掉前后空格
    cleaned = model_str.strip()

    # 如果命中黑名单（比如：上一台、刚才这台机器）
    if PRONOUN_PATTERN.match(cleaned) or cleaned in ["UNKNOWN", "未知"]:
        # 🟢 自动去数据库查最近入库的一台【在库】设备
        latest_inventory = (
            db_session.query(InventoryModel)
            .filter(InventoryModel.shop_id == shop_id, InventoryModel.status == 1) # 1: 在库
            .order_by(InventoryModel.created_at.desc())
            .first()
        )
        
        if latest_inventory:
            # 用真实设备的名称替换掉代词！
            return latest_inventory.title
        else:
            raise ValueError("没有找到最近可出售的在库设备")

    return cleaned


@shop_router.post(
    "/device/sell",
    response_model=SellDeviceResponse,  # 🌟 直接指定 Bare Payload 的 Pydantic Response 模型
    status_code=status.HTTP_200_OK,
    summary="确认设备出售出库",
)
async def confirm_sell_device(
    request: Request,
    payload: SellDeviceConfirmPayload,
    db: Session = Depends(get_db),
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
):
    # ---------------------------------------------------------
    # 1. Header 校验：缺失直接抛出 BusinessException
    # ---------------------------------------------------------
    if not x_shop_id:
        raise BusinessException(
            code=ErrorCode.MISSING_SHOP_ID,
            detail="缺少必要参数：请求头中未包含 X-Shop-Id",
            status_code=status.HTTP_400_BAD_REQUEST,
            type_url="https://api.yourdomain.com/errors/missing-shop-id",
        )

    real_model = clean_device_model(payload.model, db, x_shop_id)

    # ---------------------------------------------------------
    # 2. 幂等防重锁 (结合店铺隔离)
    # ---------------------------------------------------------
    raw_str = f"sell_{x_shop_id}_{real_model}_{payload.price}_{payload.notes}"
    lock_key = f"lock:device_sell:{hashlib.md5(raw_str.encode()).hexdigest()}"
    is_locked = redis_client.set(lock_key, "locked", ex=5, nx=True)

    if not is_locked:
        raise BusinessException(
            code=ErrorCode.DUPLICATE_REQUEST,
            detail="请勿重复提交！正在处理中...",
            status_code=status.HTTP_400_BAD_REQUEST,
            type_url="https://api.yourdomain.com/errors/duplicate-request",
        )

    try:
        # ---------------------------------------------------------
        # 3. 🛡️ 悲观排他锁 (SELECT ... FOR UPDATE) 防并发超卖
        # ---------------------------------------------------------
        query = db.query(InventoryModel).filter(
            InventoryModel.status == 1,
            InventoryModel.shop_id == x_shop_id,
            InventoryModel.stock_quantity > 0,
        )

        if real_model.isdigit():
            query = query.filter(InventoryModel.id == int(real_model))
        else:
            query = query.filter(InventoryModel.title.ilike(f"%{real_model}%"))

        # 锁定选中行记录
        device = query.with_for_update().first()

        # 双重校验：避免排队等待锁出来后库存已被上一事务扣完
        if not device or device.stock_quantity <= 0:
            raise BusinessException(
                code=ErrorCode.DEVICE_NOT_FOUND_OR_SOLD,
                detail=f"未在库存中找到可售设备或已被抢先售出：'{real_model}'",
                status_code=status.HTTP_404_NOT_FOUND,
                type_url="https://api.yourdomain.com/errors/device-not-found",
            )

        # ---------------------------------------------------------
        # 4. 核心逻辑：计算金额与安全扣减库存
        # ---------------------------------------------------------
        cost_price = float(device.purchase_price or 0)
        sell_price = payload.price
        profit = sell_price - cost_price

        device.stock_quantity -= 1
        if device.stock_quantity <= 0:
            device.stock_quantity = 0
            device.status = 2  # 已出库

        # ---------------------------------------------------------
        # 5. 写入出库单、明细及财务流水
        # ---------------------------------------------------------
        order_sn = (
            f"OUT_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"
        )
        outbound_order = OutboundOrder(
            order_sn=order_sn,
            total_amount=sell_price,
            created_at=datetime.now(),
            shop_id=x_shop_id,
        )
        db.add(outbound_order)
        db.flush()

        order_item = OutboundOrderItem(
            outbound_order_id=outbound_order.id,
            inventory_id=device.id,
            quantity=1,
            purchase_price=cost_price,
            selling_price=sell_price,
            profit=profit,
        )
        db.add(order_item)

        financial_record = FinancialRecord(
            record_sn=f"INC_{order_sn}",
            type=1,
            category="手机销售",
            amount=sell_price,
            profit=profit,
            business_type=1,
            business_id=outbound_order.id,
            payment_method=payload.payment_method,
            remark=f"设备出售出库：{device.title} | 订单号:{order_sn}",
            shop_id=x_shop_id,
            device_sn_code=device.sn_code,
        )
        db.add(financial_record)

        # 提交事务并释放行锁
        db.commit()

        # ---------------------------------------------------------
        # 6. 🌟 Bare Payload 模式：直接返回 Schema 对象或裸字典
        # ---------------------------------------------------------
        return SellDeviceResponse(
            id=device.id,
            model=device.title,
            order_sn=order_sn,
            sell_price=sell_price,
            profit=profit,
        )

    except BusinessException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.exception("【系统错误】设备确认出售失败:")
        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            detail=f"服务器内部数据错误: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            type_url="https://api.yourdomain.com/errors/internal-server-error",
        )

    finally:
        redis_client.delete(lock_key)