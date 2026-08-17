from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
# 导入你的真实模型
from src.model.models import FinancialRecord
from src.model.inventory_model import InventoryModel as Inventory

class FinancialService:

    @staticmethod
    def get_report_data(db: Session, shop_id: int,  time_range: str = "today") -> dict:
        """
        根据 FinancialRecord 财务表统计经营报表
        time_range 可选值: 'today' (今天), 'yesterday' (昨天), 'this_month' (本月)
        """
        now = datetime.now()

        # 1. 确定时间过滤条件 (start_time ~ end_time)
        if time_range == "today":
            start_time = datetime.combine(date.today(), time.min)
            end_time = datetime.combine(date.today(), time.max)
        elif time_range == "yesterday":
            yesterday = date.today() - timedelta(days=1)
            start_time = datetime.combine(yesterday, time.min)
            end_time = datetime.combine(yesterday, time.max)
        elif time_range == "this_month":
            start_time = datetime(now.year, now.month, 1, 0, 0, 0)
            end_time = datetime.combine(date.today(), time.max)
        else:
            start_time = datetime.combine(date.today(), time.min)
            end_time = datetime.combine(date.today(), time.max)

        # 2. 从 FinancialRecord 表中查询指定时间段内的所有财务记录
        records = db.query(FinancialRecord).filter(
            FinancialRecord.record_time >= start_time,
            FinancialRecord.record_time <= end_time,
            FinancialRecord.shop_id == shop_id
        ).all()

        # 3. 统计收入、支出与纯毛利
        # type: 1 - 收入, 2 - 支出
        income = sum(float(r.amount or 0) for r in records if r.type == 1)
        expense = sum(float(r.amount or 0) for r in records if r.type == 2)
        profit = sum(float(r.profit or 0) for r in records if r.type == 1)

        # 4. 统计出售台数 (统计 type == 1 且有关联设备或业务类型的流水数)
        sales_count = sum(1 for r in records if r.type == 1)

        return {
            "income": round(income, 2),        # 营业收入
            "expense": round(expense, 2),      # 进货/经营支出
            "profit": round(profit, 2),        # 销售毛利
            "sales_count": sales_count         # 出售笔数/台数
        }