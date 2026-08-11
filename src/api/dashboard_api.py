# src/api/dashboard_api.py
import time
import uuid
import logging
import json
import re
import hashlib
import ast
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.common.database import get_db # 获取数据库连接
from src.service.inventory_service import InventoryService
from datetime import datetime, date, time as dt_time
from sqlalchemy import func
from src.model.models import InventoryModel as Inventory, FinancialRecord

from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from src.core.shop_agent.system import ShopAgentSystem
from src.model.user_model import User, UserRole
from src.model.shop_model import ShopModel
from src.model.staff_model import StaffModel
from src.model.schema import CreateShopPayload, UpdateShopPayload, CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.api.auth_api import get_current_user, create_access_token
from src.common.auth import require_roles
from src.common.exceptions import BusinessException
from src.config.config import settings
from src.dependencies.permissions import allow_admin_or_manager, allow_admin, allow_all_staff
from src.model.response_models import StaffResponse

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

# ====================================================
# 店铺与员工管理 API 路由
# ====================================================

# ──────── 商家自主开店/创建店铺 API ────────
@shop_router.post("/create", summary="创建新店铺")
def create_shop(
    payload: CreateShopPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    方案 B - 商家自主开店逻辑：
    1. 在 shops 表插入新店铺记录
    2. 将当前登录用户绑定到该店铺 (user.shop_id = new_shop.id)
    3. 自动将该用户角色升级为店铺管理员/店长 (UserRole.ADMIN)
    """
    # 1. 简单校验：如果用户已经绑定了店铺，禁止重复创建（或根据需求允许创建多店）
    if getattr(current_user, "shop_id", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您已绑定店铺，无法重复创建！如需切换店铺请联系管理员。"
        )

    try:
        # 2. 落库创建店铺
        new_shop = ShopModel(
            name=payload.name,
            logo=payload.logo,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            province=payload.province,
            city=payload.city,
            district=payload.district,
            address_detail=payload.address_detail,
            is_active=True
        )
        db.add(new_shop)
        db.flush()  # 获取自动生成的 new_shop.id

        # 3. 绑定用户并升级为该店铺的创建者/店长
        current_user.shop_id = new_shop.id
        current_user.role = UserRole.ADMIN  # 自动成为店长

        db.commit()
        db.refresh(new_shop)

        return {
            "code": 200,
            "message": "店铺创建成功！已为您自动配置店长权限。",
            "data": {
                "shop_id": new_shop.id,
                "name": new_shop.name,
                "role": current_user.role
            }
        }

    except Exception as e:
        db.rollback()
        logger.exception("【API 错误】创建店铺失败:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建店铺失败: {str(e)}"
        )

# ──────── 修改店铺信息 API ────────
@shop_router.put("/update", summary="修改店铺信息")
def update_shop_info(
    payload: UpdateShopPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    修改店铺信息接口：
    - 仅允许店长/管理员 (UserRole.ADMIN 或 role == 'admin') 修改
    - 普通员工越权修改将直接被拒绝
    """
    user_role = str(getattr(current_user, "role", "staff")).lower()
    if user_role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有店长/管理员才有权限修改店铺信息！"
        )

    # 确定目标店铺 ID（默认修改用户当前绑定的店铺）
    target_shop_id = payload.shop_id or getattr(current_user, "shop_id", 1)

    # 跨店修改鉴权：防止修改其他店铺
    if payload.shop_id and payload.shop_id != getattr(current_user, "shop_id", 1):
        if user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权修改其他店铺的信息！"
            )

    shop = db.query(ShopModel).filter(ShopModel.id == target_shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应店铺，无法修改！"
        )

    # 动态更新非空字段
    update_data = payload.model_dump(exclude_unset=True, exclude={"shop_id"})
    for key, value in update_data.items():
        if value is not None:
            setattr(shop, key, value)

    try:
        db.commit()
        db.refresh(shop)
        return {
            "code": 200,
            "message": "店铺信息更新成功！",
            "data": {
                "id": shop.id,
                "name": shop.name,
                "logo": shop.logo,
                "contact_name": shop.contact_name,
                "contact_phone": shop.contact_phone,
                "address": f"{shop.province or ''}{shop.city or ''}{shop.district or ''}{shop.address_detail or ''}"
            }
        }
    except Exception as e:
        db.rollback()
        logger.exception("【API 错误】修改店铺信息失败:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )

# ──────── 🌟 新增接口 1：获取当前店铺信息 ────────
@shop_router.get("/current", summary="获取当前登录用户关联的店铺信息")
def get_current_shop_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提供给小程序【设置页/店铺信息】使用：
    优先从 shops 表查询真实店铺数据及关联员工总数。
    """
    user_shop_id = getattr(current_user, "shop_id", None) or 1

    # 1. 查询店铺信息
    shop = db.query(ShopModel).filter(ShopModel.id == user_shop_id).first()

    # 2. 统计该店铺下激活的员工总数
    staff_count = db.query(func.count(User.id)).filter(
        User.shop_id == user_shop_id,
        User.is_active == True
    ).scalar() or 1

    # 未绑定店铺，依然返回 200，data 给 None 或 null
    if not shop:
        return {
            "code": 200,
            "message": "success",
            "data": None  # 核心：用 null 表示无店铺
        }
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": shop.id,
            "name": shop.name,
            "logo": shop.logo or "",
            "contact_name": shop.contact_name or "",
            "contact_phone": shop.contact_phone or "",
            "province": shop.province or "",
            "city": shop.city or "",
            "district": shop.district or "",
            "address_detail": shop.address_detail or "",
            "staff_count": staff_count
        }
    }

# ──────── 🌟 新增接口 2：查询店铺下所有关联员工 ────────
@shop_router.get("/staff/list", summary="查询店铺下关联的所有员工")
def get_staff_list(
    shop_id: Optional[int] = Query(None, description="需要查询的目标店铺ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询指定店铺下的员工列表。
    - 开发/测试环境：超级管理员可传 shop_id 跨店切换测试。
    - 线上生产环境：严禁超管或普通用户跨租户越权查询，强行绑定当前登录用户的 shop_id。
    """
    is_production = settings.is_production  # 请确保与你的环境变量匹配
    is_super_admin = getattr(current_user, "role", None) == UserRole.ADMIN.value

    # 1. 确定最终生效的 shop_id
    target_shop_id = getattr(current_user, "shop_id", 1)

    if is_super_admin:
        if is_production:
            # 🛑 生产线上环境：严禁超管越权穿透，直接抛出权限异常或限制只能看自己的
            if shop_id and shop_id != target_shop_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="线上生产环境禁止超级管理员越权跨店查看客户员工数据！"
                )
        else:
            # 🟢 开发/测试环境：允许超管自由穿透传入 shop_id 测试
            if shop_id:
                target_shop_id = shop_id
    else:
        # 普通店员/店长：强行限制只能查自己所在店铺
        if shop_id and shop_id != target_shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权查看非本店铺的员工信息！"
            )

    # 2. 🌟 核心重构：从数据库 StaffModel (shop_staff) 表检索员工
    staff_records = db.query(StaffModel).filter(
        StaffModel.shop_id == target_shop_id
    ).all()

    # 3. 转化为小程序前端所需格式
    result_list = []
    for s in staff_records:
        result_list.append({
            "id": s.id,                           # 🌟 这是 shop_staff 的 ID，用于 generate-invite
            "name": s.name or "员工",
            "is_active": (s.status == 1),        # status==1 表示已绑定在职，0 表示待接受邀请
            "isCreator": (s.role == UserRole.ADMIN.value or s.role == "owner"), 
            "roleName": "店长" if (s.role == UserRole.ADMIN.value or s.role == "owner") else "店员",
            "role": s.role
        })

    # 兜底数据（如果数据库为空，防止小程序渲染崩掉）
    if not result_list:
        result_list = [{
            "id": current_user.id,
            "name": getattr(current_user, "nickname", None) or getattr(current_user, "username", "店长"),
            "is_active": True,
            "isCreator": True,
            "roleName": "店长",
            "role": "admin"
        }]

    return {
        "code": 200,
        "message": "success",
        "data": result_list
    }

# ==========================================
# 接口 1: 管理员新增员工档案 (未绑定 openid)
# ==========================================
@shop_router.post(
    "/staff/create",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建员工档案"
)
def create_staff(
    req: CreateStaffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(allow_admin_or_manager)
):
    if not current_user.shop_id:
            raise BusinessException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="USER_SHOP_NOT_BOUND"
            )

    # 🌟 核心重构：直接往 ShopStaff (或 StaffModel) 表插记录！
    # user_id 留空 None，完全不涉及 openid，彻底根治唯一键冲突
    new_staff = StaffModel(
        shop_id=current_user.shop_id,
        user_id=None,                 # 未接受邀请前为 None
        name=req.nickname,            # 员工姓名/备注
        role=req.role.value,
        status=0                      # 状态 0: 待认领/待接受邀请
    )
    
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)

    # 3. 直接返回 Model 实例或 Dict，FastAPI 会自动序列化为 StaffResponse
    return StaffResponse(
        id=new_staff.id,
        nickname=new_staff.name,
        role=new_staff.role,
        status=new_staff.status,
        is_active=False
    )

# ==========================================
# 接口 2: 生成邀请 Token (点击邀请按钮时调用)
# ==========================================
@shop_router.post("/staff/generate-invite")
def generate_invite(
    req: CreateInviteRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_user)
):
    # 🌟 用 req.staff_id 去查已有员工，不要读不存在的 req.name 了！
    staff = db.query(StaffModel).filter(
        StaffModel.id == req.staff_id,
        StaffModel.shop_id == req.shop_id
    ).first()

    if not staff:
        raise HTTPException(status_code=404, detail="未找到该员工档案")

    invite_token = f"INVITE_{staff.id}_{staff.shop_id}_{int(time.time())}"

    return {
        "code": 200,
        "message": "生成邀请成功",
        "data": {
            "staff_id": staff.id,
            "staff_name": staff.name,
            "invite_token": invite_token
        }
    }

# ==========================================
# 接口 3: 受邀员工接受邀请并绑定 OpenID
# ==========================================
@shop_router.post("/accept-invite")
def accept_invite(
    req: AcceptInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # current_user 是系统真正的 User 账号
):
    # 1. 解析 token (格式: INVITE_staffId_shopId_timestamp)
    try:
        parts = req.invite_token.split("_")
        staff_id = int(parts[1])
        shop_id = int(parts[2])
    except Exception:
        raise HTTPException(status_code=400, detail="无效的邀请链接")

    # 2. 🌟 修复：查员工表 StaffModel，而不是店铺表 ShopModel！
    staff_profile = db.query(StaffModel).filter(
        StaffModel.id == staff_id, 
        StaffModel.shop_id == shop_id
    ).first()

    if not staff_profile:
        raise HTTPException(status_code=404, detail="邀请信息已失效或不存在")

    if staff_profile.status == 1 and staff_profile.user_id is not None:
        raise HTTPException(status_code=400, detail="该邀请已被其他人使用")

    # 3. 🌟 优雅绑定：将 current_user.id 关联到员工档案上
    staff_profile.user_id = current_user.id
    staff_profile.status = 1  # 激活状态

    # (可选) 同步更新一下 current_user 的 shop_id，保持主表感知
    current_user.shop_id = shop_id

    db.commit()

    # 4. 签发更新后的 Token
    new_token = create_access_token(data={
        "sub": str(current_user.id),
        "role": staff_profile.role,
        "openid": current_user.openid
    })

    return {
        "code": 200,
        "message": "成功加入店铺！",
        "data": {
            "token": new_token,
            "shop_id": staff_profile.shop_id,
            "role": staff_profile.role
        }
    }

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