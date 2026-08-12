# src/api/dashboard_api.py
import time
import uuid
import logging
import json
import re
import hashlib
import ast
import jwt
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
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
from src.model.user_model import User
from src.common.dict import SystemRole, ShopRole
from src.model.shop_model import ShopModel
from src.model.staff_model import StaffModel
from src.model.schema import  CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.model.shop_schema import ShopResponse, CreateShopPayload, UpdateShopPayload
from src.api.auth_api import get_current_user, create_access_token
from src.common.exceptions import BusinessException
from src.config.config import settings
from src.dependencies.permissions import allow_admin, allow_shop_manager, allow_shop_staff
from src.model.response_models import StaffResponse
from src.model.dashboard_schema import DashboardOverviewResponse

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
from src.model.inventory_schema import StockListResponse

logger = logging.getLogger(__name__)

shop_agent = ShopAgentSystem()

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["首页看板"])

@dashboard_router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="获取首页概览数据"
)
def get_dashboard_overview(
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: Session = Depends(get_db),
    current_staff=Depends(allow_shop_manager)  # ShopRoleChecker 校验后返回当前 Staff/店铺上下文
):
    """
    提供给小程序首页【收支概览卡片】的实时统计数据：
    - 今日收入 (type=1)
    - 今日支出 (type=2)
    - 今日毛利 (sum(profit))
    - 在库设备总台数 (status=1 且数量总和)
    """
    # 1. 确定最终生效的 shop_id（优先使用 Header 传入，若未传则使用权限依赖项自动处理/降级后的 shop_id）
    target_shop_id = shop_id or getattr(current_staff, "shop_id", 1)

    # 2. 获取今天的起始与结束时间范围
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    # 3. 查询【在库设备台数】(强制加上店铺隔离条件)
    in_stock_count = db.query(
        func.coalesce(func.sum(Inventory.stock_quantity), 0)
    ).filter(
        Inventory.shop_id == target_shop_id,  # 🔒 店铺数据隔离
        Inventory.status == 1
    ).scalar()

    # 4. 计算【今日总收入】(type = 1 收入，强制加上店铺隔离条件)
    today_income = db.query(
        func.coalesce(func.sum(FinancialRecord.amount), 0.0)
    ).filter(
        FinancialRecord.shop_id == target_shop_id,  # 🔒 店铺数据隔离
        FinancialRecord.type == 1,
        FinancialRecord.record_time >= today_start,
        FinancialRecord.record_time <= today_end
    ).scalar()

    # 5. 计算【今日总支出】(type = 2 支出，强制加上店铺隔离条件)
    today_expense = db.query(
        func.coalesce(func.sum(FinancialRecord.amount), 0.0)
    ).filter(
        FinancialRecord.shop_id == target_shop_id,  # 🔒 店铺数据隔离
        FinancialRecord.type == 2,
        FinancialRecord.record_time >= today_start,
        FinancialRecord.record_time <= today_end
    ).scalar()

    # 6. 计算【今日总毛利】(仅汇总销售收入类流水的 profit 字段)
    today_profit = db.query(
        func.coalesce(func.sum(FinancialRecord.profit), 0.0)
    ).filter(
        FinancialRecord.shop_id == target_shop_id,  # 🔒 店铺数据隔离
        FinancialRecord.type == 1,
        FinancialRecord.record_time >= today_start,
        FinancialRecord.record_time <= today_end
    ).scalar()

    # 7. 遵守 Bare Payload 规范：直接返回数据字典，由 FastAPI + Pydantic 自动序列化
    return {
        "today_profit": round(float(today_profit), 2),
        "today_income": round(float(today_income), 2),
        "today_expense": round(float(today_expense), 2),
        "in_stock_devices": int(in_stock_count)
    }

# ====================================================
# 1. 确认入库 API (请求体 & 路由接口)
# ====================================================

shop_router = APIRouter(prefix="/api/v1/shop", tags=["店铺业务"])

# ====================================================
# 店铺与员工管理 API 路由
# ====================================================

# ──────── 商家自主开店/创建店铺 API ────────
@shop_router.post("/create", response_model=ShopResponse, status_code=status.HTTP_201_CREATED, summary="创建店铺")
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
    # 1. 确定 owner_id：如果未传，默认为当前登录用户
    owner_id = payload.owner_id or current_user.id

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
        current_user.role = ShopRole.OWNER

        db.commit()
        db.refresh(new_shop)

        return new_shop

    except Exception as e:
        db.rollback()
        logger.exception("【API 错误】创建店铺失败:")
        raise BusinessException(message="创建店铺失败", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
@shop_router.get(
    "/current",
    response_model=Optional[ShopResponse],  # 允许返回店铺对象或 None (JSON null)
    status_code=status.HTTP_200_OK,
    summary="获取当前登录用户关联的店铺信息"
)
def get_current_shop_info(
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提供给小程序【设置页/店铺信息】使用：
    查询当前选择/关联的真实店铺数据及员工总数。
    """
    # 1. 确定当前要查询的 shop_id：优先取 Header 传参，次之从关联关系获取
    target_shop_id = x_shop_id

    if not target_shop_id:
        # 如果 Header 没传，去 shop_staff 表查用户绑定的第一个店铺 ID
        staff_rel = db.query(StaffModel).filter(
            StaffModel.user_id == current_user.id,
            StaffModel.status == 1
        ).first()
        if staff_rel:
            target_shop_id = staff_rel.shop_id

    # 2. 未找到关联店铺，直接返回 None (JSON 会渲染为 null)
    if not target_shop_id:
        return None

    # 3. 查询店铺主数据
    shop = db.query(ShopModel).filter(ShopModel.id == target_shop_id, ShopModel.is_active == True).first()
    if not shop:
        return None

    # 4. 统计该店铺下激活的员工总数 (从 ShopStaff 表统计)
    staff_count = db.query(func.count(StaffModel.id)).filter(
        StaffModel.shop_id == target_shop_id,
        StaffModel.status == 1
    ).scalar() or 1
    shop.staff_count = staff_count

    return shop

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
    - 🌟 自动生成 Token：对待激活员工 (status==0) 自动注入 invite_token
    """
    is_production = settings.is_production  # 请确保与你的环境变量匹配
    is_super_admin = getattr(current_user, "role", None) == ShopRole.OWNER.value

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

    # 2. 从数据库 StaffModel (shop_staff) 表检索员工
    staff_records = db.query(StaffModel).filter(
        StaffModel.shop_id == target_shop_id
    ).all()

    # 3. 转化为小程序前端所需格式
    result_list = []
    for s in staff_records:
        is_active = (s.status == 1)  # status==1 表示已绑定在职，0 表示待接受邀请
        is_owner = (s.role == ShopRole.OWNER.value or s.role == "owner")
        
        # 🌟 核心增补逻辑：如果是待激活/待绑定员工，为其自动生成专属加密 invite_token
        invite_token = None
        if not is_active:
            # 💡 这里的签发逻辑请替换为你系统中生成加密 Token 的实际函数
            # 必须包含 shop_id 和 staff_id (s.id) 信息
            invite_token = create_access_token(
                data={"shop_id": target_shop_id, "staff_id": s.id}
            )

        result_list.append({
            "id": s.id,                             # shop_staff 档案 ID
            "name": s.name or "员工",
            "is_active": is_active,
            "isActive": is_active,                # 兼容驼峰与下划线命名
            "status": s.status,
            "isCreator": is_owner, 
            "roleName": "店长" if is_owner else "店员",
            "role": s.role,
            "invite_token": invite_token          # 🌟 将 Token 返回给前端
        })

    # 兜底数据（如果数据库为空，防止小程序渲染崩掉）
    if not result_list:
        result_list = [{
            "id": current_user.id,
            "name": getattr(current_user, "nickname", None) or getattr(current_user, "username", "店长"),
            "is_active": True,
            "isActive": True,
            "status": 1,
            "isCreator": True,
            "roleName": "店长",
            "role": "admin",
            "invite_token": None
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
    current_user: User = Depends(allow_shop_manager),
    # 从 Header 中提取 X-Shop-Id
    x_shop_id: str = Header(..., alias="X-Shop-Id") 
):
    # ---------------------------------------------------------
    # 1. 安全校验：Header 及数据类型校验
    # ---------------------------------------------------------
    if not x_shop_id or not x_shop_id.isdigit():
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求头缺失或非法的 X-Shop-Id"
        )

    shop_id = int(x_shop_id)

    # (可选增强) 校验当前管理员是否有权操作传入的这个 shop_id
    # 如果管理员的账号有绑定 shop_id，且与 Header 不一致，可以阻断非法越权
    if hasattr(current_user, 'shop_id') and current_user.shop_id and current_user.shop_id != shop_id:
        raise BusinessException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权管理该店铺的员工档案"
        )

    # ---------------------------------------------------------
    # 2. 🛡️ 双重防御：防 NULL 逻辑漏洞（代码层防护）
    # ---------------------------------------------------------
    # 检查当前店铺下是否已经存在“同名”的在职员工或待认领档案
    existing_staff = db.query(StaffModel).filter(
        StaffModel.shop_id == shop_id,
        StaffModel.name == req.nickname,
        StaffModel.status.in_([0, 1])  # 0: 待认领, 1: 正常在职 (过滤掉 2: 已离职/禁用)
    ).first()

    if existing_staff:
        status_text = "待接受邀请" if existing_staff.status == 0 else "在职"
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"店铺内已存在名为 '{req.nickname}' 的{status_text}员工，请勿重复创建"
        )

    # ---------------------------------------------------------
    # 3. 核心业务：预创建员工档案（绑定从 Header 传进来的 shop_id）
    # ---------------------------------------------------------
    # 获取角色字符串 (兼容 Enum 枚举和纯字符串)
    staff_role = req.role.value if hasattr(req.role, 'value') else req.role

    new_staff = StaffModel(
        shop_id=shop_id,
        user_id=None,                 # 未接受邀请前为 None
        name=req.nickname,            # 员工姓名/备注
        role=staff_role,
        status=0                      # 状态 0: 待认领/待接受邀请
    )
    
    try:
        db.add(new_staff)
        db.commit()
        db.refresh(new_staff)
    except Exception as e:
        db.rollback()
        # 防御兜底：捕获数据库唯一索引并发冲突等意外
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="创建员工档案失败，系统数据异常"
        )

    # ---------------------------------------------------------
    # 4. Bare Payload 模式返回规范 Response
    # ---------------------------------------------------------
    return StaffResponse(
        id=new_staff.id,
        nickname=new_staff.name,
        role=new_staff.role,
        status=new_staff.status,
        is_active=False
    )

# ------------------------------------------------------------------
# 2. 接口实现：GET /api/v1/shop/inventory/list
# ------------------------------------------------------------------
@shop_router.get("/inventory/list", response_model=StockListResponse)
def get_inventory_list(
    status: Optional[int] = Query(None, description="库存状态: 1-在库, 2-已售, 3-退货等"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # 校验身份并获取所属店铺
):
    """
    获取当前店铺下的设备库存列表（支持按状态筛选）
    """
    # 1. 通过 current_user.id 到 shop_staff 表中查询绑定的员工记录 (且状态必须为正常在职 status=1)
    staff_record = db.query(StaffModel).filter(
        StaffModel.user_id == current_user.id,
        StaffModel.status == 1  # 确保该员工状态正常（已接受邀请且未离职）
    ).first()

    if not staff_record:
        # RFC 7807 规范抛出 400 或 403 错误
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前用户未绑定任何店铺或暂无店铺操作权限"
        )
    
    shop_id = staff_record.shop_id
    staff_id = staff_record.id
    if not shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="当前用户未绑定任何店铺"
        )

    # 基础查询：过滤当前店铺的数据
    query = db.query(InventoryModel).filter(InventoryModel.shop_id == shop_id)

    # 如果前端传了 status 参数（如 status=1 在库设备）
    if status is not None:
        query = query.filter(InventoryModel.status == status)

    # 按创建时间/更新时间倒序
    items = query.order_by(InventoryModel.created_at.desc()).all()

    # 遵循 Bare Payload 规范，直接返回对象字典（自动被 Pydantic 序列化为 {"items": [...]}）
    return {"items": items}

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
        payload = jwt.decode(
            req.invite_token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        parts = req.invite_token.split("_")
        staff_id = payload.get("staff_id")
        shop_id = payload.get("shop_id")
    except Exception:
        raise BusinessException(status_code=400, detail="无效的邀请链接")

    # 2. 🌟 修复：查员工表 StaffModel，而不是店铺表 ShopModel！
    staff_profile = db.query(StaffModel).filter(
        StaffModel.id == staff_id, 
        StaffModel.shop_id == shop_id
    ).first()

    if not staff_profile:
        raise BusinessException(status_code=404, detail="邀请信息已失效或不存在")

    if staff_profile.status == 1 and staff_profile.user_id is not None:
        raise BusinessException(status_code=400, detail="该邀请已被其他人使用")

    # ---------------------------------------------------------
    # 3. 🌟 关键防御：防 uix_shop_user 数据库唯一键冲突
    # ---------------------------------------------------------
    # 检查当前点击链接的用户，是否已经在该店铺拥有员工身份
    already_member = db.query(StaffModel).filter(
        StaffModel.shop_id == shop_id,
        StaffModel.user_id == current_user.id
    ).first()

    if already_member:
        # 如果已经拥有身份，拦截请求，抛出 RFC 7807 400 错误
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="USER_ALREADY_MEMBER"
        )

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
        "token": new_token,
        "shop_id": staff_profile.shop_id,
        "staff_id": staff_profile.id,
        "role": staff_profile.role,
        "message": "成功加入店铺！"
    }


# ──────── 业务 B 接口 (手机店小程序) ────────
# 1. 定義標準的請求載荷（Payload）
class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None  # 允許外部傳入自訂的會話 ID，用於辨識不同用戶

@shop_router.post("/chat")
async def shop_chat(
    req: ChatPayload,
    # 🌟 1. 从 请求头(Header) 中提取 X-Shop-Id，默认可以给 None 或 抛出异常
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id"),
    # 🌟 2. 前端从 storage 拿到的 role，可以在请求头加一个 X-User-Role 传过来
    x_user_role: Optional[str] = Header("staff", alias="X-User-Role")
):
    # 校验 shop_id 是否存在
    if not x_shop_id:
        raise HTTPException(status_code=400, detail="请求头缺少 X-Shop-Id")
    # 🌟 3. 将提取到的 shop_id 和 role 塞进 LangGraph 的 configurable 字典中
    config = {
        "configurable": {
            "thread_id": req.session_id or "default_session",
            "shop_id": x_shop_id,       # 传入整数类型的 shop_id
            "role": x_user_role,         # 传入角色（如 admin, staff）
        }
    }
    
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

@shop_router.post("/device/sell", summary="确认设备出售出库")
async def confirm_sell_device(
    payload: SellDeviceConfirmPayload, 
    db: Session = Depends(get_db),
    # 🌟 提取请求头里的 X-Shop-Id
    x_shop_id: Optional[int] = Header(None, alias="X-Shop-Id")
):

    # 🌟 校验 shop_id，如果没传或者拿不到直接拦住，避免抛 500 报错
    if not x_shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="缺少必要参数：请求头中未包含 X-Shop-Id"
        )

    #2. 在你的 sell_device 处理函数里调用：
    real_model = clean_device_model(payload.model, db, x_shop_id)

    # 1. 简易 Redis 防重锁 (修改 key 前缀为 sell)
    raw_str = f"sell_{real_model}_{payload.price}_{payload.notes}"
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
            InventoryModel.shop_id == x_shop_id,
            InventoryModel.stock_quantity > 0
        )
        if real_model.isdigit():
            device = query.filter(InventoryModel.id == int(real_model)).first()
        else:
            device = query.filter(InventoryModel.title.ilike(f"%{real_model}%")).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未在库存中找到待售设备：'{real_model}'"
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
            created_at=datetime.now(),
            shop_id=x_shop_id
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
            remark=f"设备出售出库：{device.title} | 订单号:{order_sn}",
            shop_id=x_shop_id,
            device_sn_code=device.sn_code
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