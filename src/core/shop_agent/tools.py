import logging
import time
import uuid
import traceback
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine, Column, BigInteger, String, Numeric, DateTime, func, or_
from sqlalchemy.orm import declarative_base, sessionmaker
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.service.inventory_service import InventoryService
from src.service.financial_service import FinancialService
from src.common.database import SessionLocal, Base, engine
from src.model.models import (
    InventoryModel, 
    FinancialRecord, 
    OutboundOrder, 
    OutboundOrderItem, 
    Partner  # ⬅️ 必须显式 import 导入进来！
)
from src.model.tools_schema import QueryShopDataInput
from langchain_core.tools import tool, InjectedToolArg
from typing import Optional, Annotated
from langchain_core.runnables import RunnableConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# 一、 数据变更/写入类工具参数 (Slim Action Tools)
# ==========================================

class AddDeviceInput(BaseModel):
    model: str = Field(
        description="手机型号及版本容量，例如：iPhone 13 128G、华为 Mate 60 Pro 256G"
    )
    cost_price: float = Field(
        description="回收/采购成本价格（纯数字，单位元），例如：1900"
    )
    color: Optional[str] = Field(
        default="未知", description="手机颜色，例如：黑色、远峰蓝"
    )
    notes: Optional[str] = Field(
        default="二手回收", description="设备成色描述、是否有拆修或故障说明"
    )


class SellDeviceInput(BaseModel):
    model_or_id: str = Field(
        description="要出售的手机型号或设备ID，例如：iPhone 13 128G 或 15"
    )
    sell_price: float = Field(
        description="实际卖出/成交价格（纯数字，单位元），例如：2500"
    )
    payment_method: Optional[str] = Field(
        default="微信", description="客户付款方式，如：微信、支付宝、现金、刷卡"
    )
    notes: Optional[str] = Field(
        default="二手销售", description="销售备注或客户信息"
    )


# 1. 设备收机/入库解析 Tool
@tool("add_device", args_schema=AddDeviceInput)
def add_device(model: str, cost_price: float, color: str = "未知", notes: str = "二手回收") -> dict:
    """
    用于识别用户收机/进货/入库设备的意图并提取参数。
    当用户说“收了/买入/进货/录入某台手机”时，必须调用此工具提取参数。
    """
    return {
        "status": "parsed",
        "action": "in",
        "type": "in",
        "model": model,
        "cost": cost_price,
        "cost_price": cost_price,
        "color": color,
        "notes": f"颜色:{color} | {notes}" if color != "未知" else notes
    }


# 2. 设备出售/开单解析 Tool
@tool("sell_device", args_schema=SellDeviceInput)
def sell_device(model_or_id: str, sell_price: float, payment_method: str = "微信", notes: str = "二手销售") -> dict:
    """
    用于识别用户出售/开单/销售设备的意图并提取参数。
    当用户说“卖了/出售/开单/出库某台手机”时，必须调用此工具提取参数。
    """
    return {
        "status": "parsed",
        "type": "out",
        "action": "sell",
        "model": model_or_id,
        "price": sell_price,
        "model_or_id": model_or_id,
        "sell_price": sell_price,
        "payment_method": payment_method,
        "notes": notes
    }


# ==========================================
# 二、 统一数据查询万能工具 (Fat Query Tool)
# ==========================================
# ----------------------------------------------------
# 2. Tool 函数实现（聚焦分支内精细化拦截与脱敏）
# ----------------------------------------------------
@tool("query_shop_data", args_schema=QueryShopDataInput)
def query_shop_data(
    query_type: str, 
    time_range: str = "today", 
    keyword: str = "", 
    payment_method: Optional[str] = None,
    # 🌟 隐式捕获 Context（AOP 装饰器拦截通过后，这里能拿到校验后的用户信息）
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> dict:
    """
    【店铺数据查询统一入口】
    无论是查当前库存、查财务利润报表，还是查历史收货/卖货/财务流水明细，统统强制调用此函数！
    """
    # 提取角色和店铺 ID
    context = config.get("configurable", {}) if config else {}
    current_shop_id = context.get("shop_id")
    user_role = context.get("role", "staff")  # admin, manager, staff
    
    is_admin = user_role in ["admin", "manager", "boss"]

    db = SessionLocal()
    try:
        # ====================================================
        # 分支 1：查当前库存 (stock) -> 字段级脱敏拦截
        # ====================================================
        if query_type == "stock":
            items = InventoryService.query_stock_items(db, shop_id=current_shop_id, keyword=keyword)
            
            stock_list = []
            for item in items:
                data = {
                    "id": item.id,
                    "model": getattr(item, "title", getattr(item, "model", "未知设备")),
                    "spec": getattr(item, "spec", None) or "标准",
                }
                
                # 🌟 [字段级拦截] 非管理员隐藏进货成本 (cost)
                if is_admin:
                    data["cost"] = float(getattr(item, "purchase_price", getattr(item, "cost", 0)) or 0)
                
                stock_list.append(data)

            return {
                "action": "query_stock",
                "status": "success",
                "keyword": keyword,
                "total_count": len(stock_list),
                "items": stock_list,
                # 🌟 给 AI 明确的上下文提示
                "security_notice": "" if is_admin else "提示：当前视图已根据您的员工权限脱敏，隐藏了设备成本价格。"
            }

        # ====================================================
        # 分支 2：查经营报表 (report) -> 范围/指标裁剪拦截
        # ====================================================
        elif query_type == "report":
            report_data = FinancialService.get_report_data(
                db, 
                shop_id=current_shop_id, 
                time_range=time_range
            )
            time_text_map = {"today": "今日", "yesterday": "昨日", "this_month": "本月", "all": "历史累计"}
            
            # 基础经营数字（普通员工可见）
            report_body = {
                "sales_count": int(report_data.get("sales_count", 0)),
            }
            
            # 🌟 [指标级拦截] 只有管理员能看到利润、总收入和总支出
            if is_admin:
                report_body["profit"] = float(report_data.get("profit", 0.0))
                report_body["income"] = float(report_data.get("income", 0.0))
                report_body["expense"] = float(report_data.get("expense", 0.0))

            return {
                "action": "query_report",
                "status": "success",
                "time_range_text": time_text_map.get(time_range, "经营"),
                "report": report_body,
                "security_notice": "" if is_admin else "提示：由于角色权限限制，仅展示销量数据，利润与财务汇总已屏蔽。"
            }

        # ====================================================
        # 分支 3：查历史明细 (inbound / outbound / finance)
        # ====================================================
        elif query_type in ["inbound", "outbound", "finance"]:
            # 🌟 [时间范围降级拦截]：普通员工查历史明细最多只能看近 7 天/今天，禁止跨月查全部
            if not is_admin and time_range == "all":
                time_range = "this_month"  # 强制将 'all' 降级为 'this_month'
                range_degraded = True
            else:
                range_degraded = False

            # 解析时间
            now = datetime.now()
            start_time, end_time = None, None
            if time_range == "today":
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now
            elif time_range == "yesterday":
                yesterday = now - timedelta(days=1)
                start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_range == "this_month":
                start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_time = now

            items_result = []

            # 3.A 历史入库 (inbound)
            if query_type == "inbound":
                query = db.query(InventoryModel).filter(InventoryModel.shop_id == current_shop_id)
                if start_time and end_time:
                    query = query.filter(InventoryModel.in_stock_time.between(start_time, end_time))
                if keyword:
                    query = query.filter(InventoryModel.title.ilike(f"%{keyword}%"))
                
                records = query.order_by(InventoryModel.in_stock_time.desc()).all()
                for item in records:
                    row = {
                        "id": item.id,
                        "model": item.title,
                        "spec": item.spec or "标准",
                        "time": item.in_stock_time.strftime("%Y-%m-%d %H:%M") if item.in_stock_time else "",
                        "remark": item.remark or ""
                    }
                    # 🌟 进货价脱敏
                    if is_admin:
                        row["purchase_price"] = float(item.purchase_price or 0)
                    items_result.append(row)

            # 3.B 历史财务流水 (finance)
            elif query_type == "finance":
                query = db.query(FinancialRecord).filter(FinancialRecord.shop_id == current_shop_id)
                if start_time and end_time:
                    query = query.filter(FinancialRecord.record_time.between(start_time, end_time))
                if payment_method:
                    query = query.filter(FinancialRecord.payment_method == payment_method)
                if keyword:
                    query = query.filter(or_(FinancialRecord.category.ilike(f"%{keyword}%"), FinancialRecord.remark.ilike(f"%{keyword}%")))

                records = query.order_by(FinancialRecord.record_time.desc()).all()
                items_result = [
                    {
                        "id": item.id,
                        "sn": item.record_sn,
                        "type": "收入" if item.type == 1 else "支出",
                        "category": item.category,
                        "amount": float(item.amount or 0),
                        "payment_method": item.payment_method,
                        "time": item.record_time.strftime("%Y-%m-%d %H:%M") if item.record_time else ""
                    }
                    for item in records
                ]

            # 3.C 历史销售 (outbound)
            elif query_type == "outbound":
                query = db.query(OutboundOrderItem, OutboundOrder, InventoryModel)\
                 .select_from(OutboundOrderItem)\
                 .outerjoin(OutboundOrder, OutboundOrderItem.outbound_order_id == OutboundOrder.id)\
                 .outerjoin(InventoryModel, OutboundOrderItem.inventory_id == InventoryModel.id)\
                 .filter(OutboundOrder.shop_id == current_shop_id)

                if start_time and end_time:
                    query = query.filter(OutboundOrder.created_at.between(start_time, end_time))
                if keyword:
                    query = query.filter(InventoryModel.title.ilike(f"%{keyword}%"))

                records = query.order_by(OutboundOrder.created_at.desc()).all()

                for item in records:
                    row = {
                        "id": item.InventoryModel.id if item.InventoryModel else item.OutboundOrderItem.id,
                        "model": item.InventoryModel.title if item.InventoryModel else "设备已删除/未知型号",
                        "spec": (item.InventoryModel.spec if item.InventoryModel else None) or "Standard",
                        "selling_price": float(item.OutboundOrderItem.selling_price or 0), # 售价放行
                        "time": item.OutboundOrder.created_at.strftime("%Y-%m-%d %H:%M") if (item.OutboundOrder and item.OutboundOrder.created_at) else ""
                    }
                    # 🌟 [利润脱敏] 仅管理员可看该单的利润 (profit)
                    if is_admin:
                        row["profit"] = float(item.OutboundOrderItem.profit or 0)
                    
                    items_result.append(row)

            # 拼接给 AI 的交互提示文字
            notice_msg = ""
            if range_degraded:
                notice_msg += "（注：非管理员角色暂不支持全量历史查询，已为您自动切换为【本月】数据）"
            if not is_admin:
                notice_msg += "（注：部分敏感财务利润字段已根据权限隐藏）"

            return {
                "action": "universal_query",
                "status": "success",
                "target": query_type,
                "time_range": time_range,
                "total_count": len(items_result),
                "items": items_result,
                "security_notice": notice_msg.strip()
            }

        else:
            return {"status": "error", "message": f"未知的查询类型: {query_type}", "total_count": 0, "items": []}

    except Exception as e:
        logger.error(f"❌ [query_shop_data] 查询报错: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"系统内部查询异常: {str(e)}", "total_count": 0, "items": []}
    finally:
        db.close()


# 工具导出列表（用于绑定给 Gemini / LangChain）
tools = [add_device, sell_device, query_shop_data]


if __name__ == "__main__":
    # 本地测试样例：
    print("1. 测试查库存:", query_shop_data(query_type="stock", keyword="13"))
    print("2. 测试查报表:", query_shop_data(query_type="report", time_range="today"))
    print("3. 测试查销售明细:", query_shop_data(query_type="outbound", time_range="this_month"))