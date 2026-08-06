import os
import logging
from sqlalchemy import create_engine, Column, BigInteger, String, Numeric, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import or_

# 配置日志（如果在项目入口已经配置过 logging，这里直接 getLogger 即可）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ----------------------------------------------------
# 2. 定义 ORM 模型 (对应前面设计的 inventory 库存表)
# ----------------------------------------------------
class InventoryModel(Base):
    __tablename__ = "inventory"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)
    purchase_price = Column(Numeric(10, 2), nullable=False, default=0.00)
    spec = Column(String(100), nullable=True)
    remark = Column(String(255), nullable=True)
    category = Column(BigInteger, default=2)  # 2-二手机
    status = Column(BigInteger, default=1)    # 1-在库
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 自动创建表结构（如果表不存在）
Base.metadata.create_all(bind=engine)

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

# ---- 定义 LangChain 工具 ----

@tool("add_device", args_schema=AddDeviceInput)
def add_device(model: str, cost_price: float, color: str = "未知", notes: str = "二手回收") -> str:
    """
    用于登记/录入收到的二手手机或新机入库信息。
    当用户说“收了/买入/进货/录入某台手机”时，必须调用此工具提取参数。
    """
    db = SessionLocal()
    try:
        # 创建数据库记录
        new_device = InventoryModel(
            title=model,
            purchase_price=cost_price,
            spec=f"颜色:{color}",
            remark=notes,
            category=2,  # 默认二手机
            status=1     # 默认在库
        )
        
        # 写入 PostgreSQL
        db.add(new_device)
        db.commit()
        db.refresh(new_device)  # 获取 PG 生成的自增 ID
        
        return (f"【系统提示】设备已成功入库并存入 PostgreSQL！"
                f"数据库ID={new_device.id}, 型号={new_device.title}, "
                f"成本={new_device.purchase_price}元, 颜色={color}, 备注={notes}")

    except Exception as e:
        db.rollback()  # 发生异常时回滚事务
        # 1. 在终端/日志文件中打印完整的错误堆栈信息
        logger.exception(f"【数据库操作异常】设备入库失败 (型号: {model}):")
        return f"【系统提示】设备入库失败，数据库错误：{str(e)}"
        
    finally:
        db.close()     # 确保关闭 Session 连接

@tool("query_stock", args_schema=QueryStockInput)
def query_stock(keyword: str) -> str:
    """
    用于查询店内现有库存情况。
    当用户询问“店内还有没有某款手机”、“查询库存”、“查看在库设备”时调用。
    """
    db = SessionLocal()
    try:
        # 基础查询：只查在库状态的设备 (status=1)
        query = db.query(InventoryModel).filter(InventoryModel.status == 1)

        # 如果传了关键词，对标题(title)、规格(spec)、备注(remark) 进行模糊匹配
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    InventoryModel.title.ilike(kw),  # ilike 不区分大小写
                    InventoryModel.spec.ilike(kw),
                    InventoryModel.remark.ilike(kw)
                )
            )

        # 按入库时间倒序排列
        items = query.order_by(InventoryModel.id.desc()).all()

        # 如果查不到数据
        if not items:
            if keyword:
                return f"【系统提示】未找到与关键词 '{keyword}' 匹配的在库设备。"
            return "【系统提示】当前暂无任何在库设备。"

        # 格式化输出查询结果
        result_lines = [f"【系统提示】为您查到匹配关键词 '{keyword}' 的在库设备 (共 {len(items)} 台)："]
        
        for item in items:
            # 格式化分类显示：1-新机, 2-二手机, 3-配件
            cat_map = {1: "新机", 2: "二手机", 3: "配件"}
            cat_str = cat_map.get(item.category, "其他")
            
            line = (
                f"- [ID: {item.id}] {item.title} ({cat_str}) | "
                f"规格: {item.spec or '无'} | "
                f"成本价: {item.purchase_price}元 | "
                f"备注: {item.remark or '无'}"
            )
            result_lines.append(line)

        return "\n".join(result_lines)

    except Exception as e:
        db.rollback()
        logger.exception(f"【数据库操作异常】查询库存失败 (关键词: {keyword}):")
        return f"【系统提示】查询库存失败，数据库错误：{str(e)}"

    finally:
        db.close()