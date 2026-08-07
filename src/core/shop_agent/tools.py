
import logging
import time
import uuid
import traceback
from sqlalchemy import create_engine, Column, BigInteger, String, Numeric, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import or_
from src.service.inventory_service import InventoryService
from src.service.financial_service import FinancialService
from src.common.database import SessionLocal, Base, engine
from src.model.models import InventoryModel, FinancialRecord



# 配置日志（如果在项目入口已经配置过 logging，这里直接 getLogger 即可）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)





# ---- 定义参数 Pydantic 模型 ----

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

class QueryStockInput(BaseModel):
    keyword: str = Field(
        description="查询库存的手机型号关键字，例如：iPhone 13"
    )

# 💰 1. 新增：出售设备参数定义
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

# ---- 2. 瘦身后的 Tool（纯解析提取，不连 DB） ----
@tool("add_device", args_schema=AddDeviceInput)
def add_device(model: str, cost_price: float, color: str = "未知", notes: str = "二手回收") -> dict:
    """
    用于识别用户收机/进货/入库设备的意图并提取参数。
    当用户说“收了/买入/进货/录入某台手机”时，必须调用此工具提取参数。
    """
    # 纯数据提取返回，完全不碰数据库！
    return {
        "status": "parsed",
        "action": "in",         # 🌟 关键修改：从 "stock_in" 改为 "in"，与前端 WXML 匹配
        "type": "in",           # 🌟 补上 type: "in" 双重保险
        "model": model,
        "cost": cost_price,     # 🌟 补上 cost 字段
        "cost_price": cost_price,
        "color": color,
        "notes": f"颜色:{color} | {notes}" if color != "未知" else notes
    }

# ---- 2. 极简 Tool：完全不碰数据库，只做解析提取 ----
@tool("sell_device", args_schema=SellDeviceInput)
def sell_device(model_or_id: str, sell_price: float, payment_method: str = "微信", notes: str = "二手销售") -> dict:
    """
    用于识别用户出售/开单/销售设备的意图并提取参数。
    当用户说“卖了/出售/开单/出库某台手机”时，必须调用此工具提取参数。
    """
    # 返回统一给前端渲染的标准 JSON 格式
    return {
        "status": "parsed",
        "type": "out",             # 🌟 明确标记类型为出库 (out)
        "action": "sell",
        "model": model_or_id,      # 🌟 映射标准字段名 model
        "price": sell_price,       # 🌟 映射标准字段名 price
        "model_or_id": model_or_id,
        "sell_price": sell_price,
        "payment_method": payment_method,
        "notes": notes
    }

# ==========================================
# 1. 查询库存 Tool (query_stock)
# ==========================================
class QueryStockInput(BaseModel):
    keyword: str = Field(
        default="",
        description="搜索关键词，如手机型号、品牌、规格，例如 '13 Pro'，如果用户没说具体型号或查询全部库存则填空字符串 ''"
    )

@tool("query_stock", args_schema=QueryStockInput)
def query_stock(keyword: str = "") -> dict:
    """用于查询店内现有设备库存列表。
    当用户询问‘库里现在有啥’、‘查库存’、‘有什么手机’、‘还剩哪些机子’时强制调用此函数。
    若用户未指定具体型号，keyword 传空字符串 '' 即可查询全部在库设备。
    """
    db = SessionLocal()
    try:
        # 如果 keyword 为空，Service 层应当返回所有 status=在库 的设备
        items = InventoryService.query_stock_items(db, keyword=keyword)

        stock_list = [
            {
                "id": item.id,
                "model": getattr(item, "title", getattr(item, "model", "未知设备")),
                "spec": getattr(item, "spec", None) or "标准",
                "cost": float(getattr(item, "purchase_price", getattr(item, "cost", 0)) or 0)
            }
            for item in items
        ]

        return {
            "action": "query_stock",
            "status": "success",
            "keyword": keyword,
            "total_count": len(stock_list),
            "items": stock_list
        }
    except Exception as e:
        print(f"\n❌ [query_stock] 运行报错: {str(e)}")
        traceback.print_exc()

        return {
            "action": "query_stock",
            "status": "error",
            "message": f"查询库存失败，错误原因: {str(e)}",
            "keyword": keyword,
            "total_count": 0,
            "items": []
        }
    finally:
        db.close()


# ==========================================
# 2. 查询财务报表 Tool (query_report)
# ==========================================
class QueryReportInput(BaseModel):
    time_range: str = Field(
        default="today", 
        description="时间范围：'today'(今天), 'yesterday'(昨天), 'this_month'(本月)"
    )

@tool("query_report", args_schema=QueryReportInput)
def query_report(time_range: str = "today") -> dict:
    """用于查询店铺经营报表、销售利润、收支统计。
    当用户询问‘今天赚了多少钱’、‘本月报表’、‘昨天卖了多少’时调用。
    注意：切勿在用户询问‘库存有什么’、‘查库存’时调用此函数！
    """
    db = SessionLocal()
    try:
        # 调用 Service 层获取财务统计数据
        report_data = FinancialService.get_report_data(db, time_range=time_range)

        time_text_map = {"today": "今日", "yesterday": "昨日", "this_month": "本月"}

        return {
            "action": "query_report",
            "status": "success",
            "time_range_text": time_text_map.get(time_range, "经营"),
            "report": {
                "profit": float(report_data.get("profit", 0.0)),    # 纯毛利
                "income": float(report_data.get("income", 0.0)),    # 总收入
                "expense": float(report_data.get("expense", 0.0)),  # 总支出
                "sales_count": int(report_data.get("sales_count", 0)),  # 出售台数
            },
        }
    except Exception as e:
        # 1. 在终端/控制台打印详细的报错堆栈信息
        print(f"\n❌ [query_report] 运行报错: {str(e)}")
        traceback.print_exc()

        # 2. 返回包含错误状态的字典，防止前端或 LLM 崩溃
        return {
            "action": "query_report",
            "status": "error",
            "message": f"查询报表失败，错误原因: {str(e)}",
            "report": {"profit": 0.0, "income": 0.0, "expense": 0.0, "sales_count": 0},
        }
    finally:
        db.close()

if __name__ == "__main__":
    res = query_report(time_range="today")
    print("手动测试结果：", res)