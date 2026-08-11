from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from src.common.dict import ShopRole

class QueryShopDataInput(BaseModel):
    query_type: str = Field(
        ...,
        description="""查询类型（必填）：
        - 'stock': 查当前在库设备/库存；
        - 'report': 查经营报表、利润、收入支出汇总数字；
        - 'inbound': 查历史进货/收机明细列表；
        - 'outbound': 查历史销售/出库/卖出明细列表；
        - 'finance': 查财务收支流水列表。
        """
    )
    time_range: Optional[str] = Field(
        "today", 
        description="时间范围（查库存时可忽略）：'today'(今天), 'yesterday'(昨天), 'this_month'(本月), 'all'(全部时间)"
    )
    keyword: Optional[str] = Field(
        "", 
        description="搜索关键词：如手机型号('iPhone 13')、客户姓名或备注信息等"
    )
    payment_method: Optional[str] = Field(
        None,
        description="支付方式过滤：如 '微信', '支付宝', '现金'"
    )