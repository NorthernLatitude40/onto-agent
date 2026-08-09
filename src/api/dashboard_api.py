# src/api/dashboard_api.py
import time
import uuid
import logging
import json
import re
import hashlib
import ast
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.common.database import get_db # 获取数据库连接
from src.service.inventory_service import InventoryService
from datetime import datetime, date, time as dt_time
from sqlalchemy import func
from src.model.models import InventoryModel as Inventory, FinancialRecord

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from src.core.shop_agent.system import ShopAgentSystem
from src.model.user_model import User, UserRole
from src.api.auth_api import get_current_user
from src.common.auth import require_roles

# 引入你的数据库连接、Session依赖与 ORM 模型
from src.common.database import get_db
from src.model.models import (
    InventoryModel, 
    FinancialRecord, 
    OutboundOrder, 
    OutboundOrderItem, 
    Partner  # ⬅️ 必须显式 import 导入进来！
)
from src.common.redis_client import redis_client

logger = logging.getLogger(__name__)

shop_agent = ShopAgentSystem()

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["首页看板"])

@dashboard_router.get("/overview", summary="获取首页概览数据")
def get_dashboard_overview(db: Session = Depends(get_db),
                        current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MANAGER]))
                           ):
    """
    提供给小程序首页【收支概览卡片】的实时统计数据：
    - 今日收入 (type=1)
    - 今日支出 (type=2)
    - 今日毛利 (sum(profit))
    - 在库设备总台数 (status=1 且数量总和)
    """
    # 1. 获取今天的起始与结束 UTC/本地时间范围
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    # 2. 查询【在库设备台数】 (累加 stock_quantity，兼容批次库存)
    # 假设 inventory.status = 1 表示在库
    in_stock_count = db.query(
        func.coalesce(func.sum(Inventory.stock_quantity), 0)
    ).filter(
        Inventory.status == 1
    ).scalar()

    # 3. 计算【今日总收入】 (type = 1 收入)
    today_income = db.query(
        func.coalesce(func.sum(FinancialRecord.amount), 0.0)
    ).filter(
        FinancialRecord.type == 1,
        FinancialRecord.record_time >= today_start,
        FinancialRecord.record_time <= today_end
    ).scalar()

    # 4. 计算【今日总支出】 (type = 2 支出)
    today_expense = db.query(
        func.coalesce(func.sum(FinancialRecord.amount), 0.0)
    ).filter(
        FinancialRecord.type == 2,
        FinancialRecord.record_time >= today_start,
        FinancialRecord.record_time <= today_end
    ).scalar()

    # 5. 计算【今日总毛利】 (仅汇总销售收入类流水的 profit 字段)
    today_profit = db.query(
        func.coalesce(func.sum(FinancialRecord.profit), 0.0)
    ).filter(
        FinancialRecord.type == 1,  # 🌟 关键：只统计销售/收入流水，过滤采购/支出流水
        FinancialRecord.record_time >= today_start,
        FinancialRecord.record_time <= today_end
    ).scalar()

    # 6. 构造小程序需要的数据格式返回
    return {
        "code": 200,
        "message": "success",
        "data": {
            "today_profit": round(float(today_profit), 2),
            "today_income": round(float(today_income), 2),
            "today_expense": round(float(today_expense), 2),
            "in_stock_devices": int(in_stock_count)
        }
    }

# ====================================================
# 1. 确认入库 API (请求体 & 路由接口)
# ====================================================

shop_router = APIRouter(prefix="/api/v1/shop", tags=["店铺业务"])

# ──────── 业务 B 接口 (手机店小程序) ────────
# 1. 定義標準的請求載荷（Payload）
class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None  # 允許外部傳入自訂的會話 ID，用於辨識不同用戶

@shop_router.post("/chat")
async def shop_chat(req: ChatPayload):
    config = {"configurable": {"thread_id": req.session_id}}
    
    # 执行 Agent
    result = await shop_agent.graph.ainvoke({"messages": [("user", req.message)]}, config)
    messages = result["messages"]
    last_msg = messages[-1]
    
    # 1. 提取 reply 文本
    raw_content = last_msg.content or ""
    if isinstance(raw_content, list):
        text_parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in raw_content]
        raw_content = "".join(text_parts)
    elif not isinstance(raw_content, str):
        raw_content = str(raw_content)

    reply_text = raw_content
    parsed_data = None

    # 2. 倒序查找【本次调用最新触发的 ToolMessage】
    for msg in reversed(messages):
        # 如果在倒序遍历过程中先碰到了用户输入的消息，说明已经退出了本次对话的范围，直接停止查找
        if getattr(msg, "type", None) == "user" or msg.__class__.__name__ == "HumanMessage":
            break

        # 寻找 ToolMessage（工具返回的结果）
        if getattr(msg, "type", None) == "tool" or msg.__class__.__name__ == "ToolMessage":
            content = getattr(msg, "content", None)
            
            if isinstance(content, dict):
                parsed_data = content
            elif isinstance(content, str) and content.strip():
                try:
                    # 优先用标准 JSON 反序列化
                    parsed_data = json.loads(content)
                except Exception:
                    try:
                        # 兜底用 ast 安全解析 Python 字典字符串格式
                        parsed_data = ast.literal_eval(content)
                    except Exception:
                        pass
            
            # 只要找到了本次对话最新的 Tool 结果（不论是 query_stock 还是 query_report），就立即跳出循环
            if parsed_data:
                break

    # 3. 兜底：如果 ToolMessage 里没拿到，再尝试从 last_msg 的 json 格式或 tool_calls 提取
    if not parsed_data:
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_content, re.DOTALL) or \
                     re.search(r'(\{.*?\})', raw_content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                reply_text = data.get("reply", reply_text)
                parsed_data = data.get("parsedData", data)
            except Exception:
                pass

    return {
        "reply": reply_text,
        "parsedData": parsed_data
    }

class AddDeviceConfirmPayload(BaseModel):
    model: str = Field(..., description="设备型号，如：iPhone 13 128G")
    cost: float = Field(..., description="采购/回收成本价")
    color: Optional[str] = Field(default="未知", description="设备颜色")
    notes: Optional[str] = Field(default="二手回收", description="备注信息")


@shop_router.post("/device/add", summary="确认设备入库落库")
async def confirm_add_device(
    payload: AddDeviceConfirmPayload, 
    db: Session = Depends(get_db)
):
    """
    前端点击【确认入库】卡片时调用的接口：
    1. 在 inventory 表创建一条在库记录 (status=1)
    2. 在 financial_record 表创建一条支出流水 (type=2)
    """
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
            status=1     # 1 - 在库
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
            remark=f"设备回收入库：{payload.model} ({payload.notes or ''})"
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


@shop_router.post("/device/sell", summary="确认设备出售出库")
async def confirm_sell_device(
    payload: SellDeviceConfirmPayload, 
    db: Session = Depends(get_db)
):
    # 1. 简易 Redis 防重锁 (修改 key 前缀为 sell)
    raw_str = f"sell_{payload.model}_{payload.price}_{payload.notes}"
    lock_key = f"lock:device_sell:{hashlib.md5(raw_str.encode()).hexdigest()}"
    is_locked = redis_client.set(lock_key, "locked", ex=5, nx=True)

    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请勿重复提交！正在处理中..."
        )

    try:
        # 2. 查找待售设备
        query = db.query(InventoryModel).filter(
            InventoryModel.status == 1,
            InventoryModel.stock_quantity > 0
        )
        if payload.model.isdigit():
            device = query.filter(InventoryModel.id == int(payload.model)).first()
        else:
            device = query.filter(InventoryModel.title.ilike(f"%{payload.model}%")).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未在库存中找到待售设备：'{payload.model}'"
            )

        # 3. 计算金额
        cost_price = float(device.purchase_price or 0)
        sell_price = payload.price
        profit = sell_price - cost_price

        # 4. 扣减库存
        device.stock_quantity -= 1
        if device.stock_quantity <= 0:
            device.stock_quantity = 0
            device.status = 2  # 已出库

        # ----------------------------------------------------
        # 🌟 核心规范修改 1：写入 OutboundOrder (出库主单)
        # ----------------------------------------------------
        order_sn = f"OUT_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"
        outbound_order = OutboundOrder(
            order_sn=order_sn,
            total_amount=sell_price,
            created_at=datetime.now()
        )
        db.add(outbound_order)
        db.flush()  # 刷入数据库以获取 outbound_order.id

        # ----------------------------------------------------
        # 🌟 核心规范修改 2：写入 OutboundOrderItem (出库明细)
        # ----------------------------------------------------
        order_item = OutboundOrderItem(
            outbound_order_id=outbound_order.id,
            inventory_id=device.id,
            quantity=1,
            purchase_price=cost_price,  # 🌟 这里改为 purchase_price
            selling_price=sell_price,   # 实际成交单价
            profit=profit               # 单项毛利
        )
        db.add(order_item)

        # ----------------------------------------------------
        # 🌟 核心规范修改 3：写入 FinancialRecord (财务流水)
        # ----------------------------------------------------
        financial_record = FinancialRecord(
            record_sn=f"INC_{order_sn}",
            type=1,  # 收入
            category="手机销售",
            amount=sell_price,
            profit=profit,
            business_type=1,
            business_id=outbound_order.id,  # 此时关联的是出库单 ID
            payment_method=payload.payment_method,
            remark=f"设备出售出库：{device.title} | 订单号:{order_sn}"
        )
        db.add(financial_record)

        # 5. 提交事务
        db.commit()

        return {
            "code": 200,
            "message": "设备出售成功！已生成出库单与财务记账。",
            "data": {
                "id": device.id,
                "model": device.title,
                "order_sn": order_sn,
                "sell_price": sell_price,
                "profit": profit
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        redis_client.delete(lock_key)
        logger.exception("【API 错误】设备确认出售失败:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"出售失败: {str(e)}"
        )