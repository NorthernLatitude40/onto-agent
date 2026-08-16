import time
import httpx
import jwt
from datetime import datetime, date, time as dt_time
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request, Path
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy.exc import IntegrityError

from src.common.database import get_db
from src.model.staff_model import StaffModel
from src.model.clark_schema import StaffUpdateSchema, StaffResponse
from src.dependencies.permissions import allow_shop_manager
from src.model.user_model import UserModel
from src.config.config import settings
from src.common.dict import ShopRole
from src.api.auth_api import get_current_user, create_access_token
from src.model.schema import  CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.common.exceptions import BusinessException
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from src.common.i18n import ErrorCode, get_i18n_message

# 假設你有一個獲取當前請求用戶資訊的 Dependency
from src.api.auth_api import get_current_user 

router = APIRouter()

# ==========================================
# 接口 1: 管理员新增员工档案 (未绑定 openid)
# ==========================================
# ==========================================
# 接口 1: 管理员新增员工档案 (重构版：单表逻辑，移除中间表)
# ==========================================
@router.post(
    "/create",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建员工档案"
)
def create_staff(
    req: CreateStaffRequest,
    db: Session = Depends(get_db),
    current_user: StaffModel = Depends(allow_shop_manager),
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

    # ---------------------------------------------------------
    # 2. 🛡️ 精准查重：直接在单表【当前店铺】范围内查重 (无需 JOIN)
    # ---------------------------------------------------------
    existing_staff = db.query(StaffModel).filter(
        StaffModel.shop_id == shop_id,
        StaffModel.name == req.nickname,
        StaffModel.status.in_([0, 1])  # 0: 待绑定/待接受邀请, 1: 正常在职 (过滤 2: 已离职/禁用)
    ).first()

    if existing_staff:
        status_text = "待接受邀请" if existing_staff.status == 0 else "在职"
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"店铺内已存在名为 '{req.nickname}' 的{status_text}员工，请勿重复创建"
        )

    # ---------------------------------------------------------
    # 3. 核心业务：创建员工记录 (shop_id、role、status 全部归入单表)
    # ---------------------------------------------------------
    # 获取角色字符串 (兼容 Enum 枚举和纯字符串)
    staff_role = req.role.value if hasattr(req.role, 'value') else req.role

    try:
        # 直接创建 Staff 记录，预创建时 user_id 为 None，status 为 0 (待绑定)
        new_staff = StaffModel(
            shop_id=shop_id,              # 所属店铺
            user_id=None,                 # 未绑定微信前为 None
            name=req.nickname,            # 员工姓名/备注
            phone=getattr(req, 'phone', None), # 如果 Request 中有 phone，可同步存入（用于绑定匹配）
            role=staff_role,              # 员工角色
            status=0                      # 0: 待认领/待接受邀请
        )
        
        db.add(new_staff)
        db.commit()      # 🌟 单表写入，原子性极强，无需 flush
        db.refresh(new_staff)

    except IntegrityError:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="创建失败，该店铺下员工数据已存在"
        )
    except Exception as e:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"系统异常，创建员工失败: {str(e)}"
        )

    # ---------------------------------------------------------
    # 4. 返回规范 Response
    # ---------------------------------------------------------
    return StaffResponse(
        id=new_staff.id,
        nickname=new_staff.name,
        role=new_staff.role,
        status=new_staff.status,
        is_active=(new_staff.status == 1) # 只有正式激活绑定后才是 active
    )

# ==========================================
# 接口: 统一更新员工资讯/状态/角色 (重构版：单表逻辑，移除中间表)
# ==========================================
@router.put("", response_model=StaffResponse, summary="统一更新员工资讯/状态/角色")
def update_staff(
    payload: StaffUpdateSchema,
    staff_id: int = Header(..., alias="X-Staff-Id"), # 🌟 直接从 Header 提取
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="当前选择的店铺ID"),
    db: Session = Depends(get_db),
    current_user: StaffModel = Depends(allow_shop_manager), # 当前操作者的 StaffModel 实例
):
    # ---------------------------------------------------------
    # 0. 确定当前操作的店铺 ID
    # ---------------------------------------------------------
    target_shop_id = shop_id or getattr(current_user, "shop_id", 1)

    # ---------------------------------------------------------
    # 1. 单表查询【目标员工】在【当前店铺】的档案 (StaffModel)
    # ---------------------------------------------------------
    target_staff = db.query(StaffModel).filter(
        StaffModel.id == payload.id,
        StaffModel.shop_id == target_shop_id
    ).first()

    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="找不到该员工档案或该员工不属于当前店铺"
        )

    # ---------------------------------------------------------
    # 2. 提取前端传进来的有效更新字段 (过滤未传递的 None)
    # ---------------------------------------------------------
    update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)

    # ---------------------------------------------------------
    # 3. 🛡️ 越权保护：角色变更安全校验
    # ---------------------------------------------------------
    operator_role = current_user.role if current_user else None

    if "role" in update_data and update_data["role"] is not None:
        new_role_val = update_data["role"]
        new_role_str = new_role_val.value if hasattr(new_role_val, "value") else str(new_role_val)
        
        # 店长 (manager) 不能修改店主 (owner) 的角色，也不能将别人提升为店主 (owner)
        if operator_role == "manager":
            if target_staff.role == "owner" or new_role_str == "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="权限不足：店长(manager)无法变更店主(owner)的角色或提升他人为店主"
                )
        
        # 覆写处理后的字符串类型 role
        update_data["role"] = new_role_str

    # ---------------------------------------------------------
    # 4. 单表动态数据更新 (合并个人信息与岗位属性)
    # ---------------------------------------------------------
    # 允许更新的字段列表：name, phone, role, status 等
    allowed_fields = {"name", "phone", "role", "status"}
    
    for field, value in update_data.items():
        if field in allowed_fields and value is not None:
            # 兼容带有 enum 的属性
            val = value.value if hasattr(value, "value") else value
            setattr(target_staff, field, val)

    # ---------------------------------------------------------
    # 5. 一次性原子提交更新
    # ---------------------------------------------------------
    try:
        db.add(target_staff)
        db.commit()
        db.refresh(target_staff)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新员工失败: {str(e)}"
        )

    # ---------------------------------------------------------
    # 6. 组装并返回规范 Response
    # ---------------------------------------------------------
    return StaffResponse(
        id=target_staff.id,
        nickname=target_staff.name,
        role=target_staff.role,
        status=target_staff.status,
        is_active=(target_staff.status == 1)
    )

# ──────── 🌟 2：查询店铺下所有关联员工 (重构版：单表逻辑，移除中间表) ────────
@router.get("", summary="查询店铺下关联的所有员工")
def get_staff_list(
    x_shop_id: int = Header(..., alias="X-Shop-Id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    查询指定店铺下的员工列表。
    - 开发/测试环境：超级管理员可跨店切换测试。
    - 线上生产环境：严禁跨租户越权查询，必须校验当前登录用户在该店铺有有效档案。
    - 🌟 自动生成 Token：对待激活员工 (status==0) 自动注入 invite_token
    """
    is_production = getattr(settings, "is_production", True)
    is_super_admin = getattr(current_user, "role", None) == ShopRole.OWNER.value
    target_shop_id = x_shop_id

    # ---------------------------------------------------------
    # 1. 权限拦截与鉴权：检查当前用户在目标店铺中是否有【在职】的员工档案
    # ---------------------------------------------------------
    current_staff_profile = db.query(StaffModel).filter(
        StaffModel.shop_id == target_shop_id,
        StaffModel.user_id == current_user.id, # 使用 user_id 匹配当前登录的微信账号
        StaffModel.status == 1                 # 必须是正式激活在职状态
    ).first()

    # 权限判定逻辑
    if not current_staff_profile:
        # 如果查不到在职档案，判断是否允许超管穿透
        if is_super_admin and not is_production:
            pass # 🟢 开发/测试环境：允许超管越权查看
        else:
            # 🛑 生产环境 或 普通员工：严禁越权
            error_msg = "线上生产环境禁止跨店查看数据！" if is_super_admin else "您无权管理该店铺的员工档案或身份已失效"
            raise BusinessException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )

    # ---------------------------------------------------------
    # 2. 从 StaffModel 单表检索该店铺所有员工
    # ---------------------------------------------------------
    staff_records = db.query(StaffModel).filter(
        StaffModel.shop_id == target_shop_id
    ).all()

    # ---------------------------------------------------------
    # 3. 转化为小程序前端所需格式
    # ---------------------------------------------------------
    result_list = []
    for s in staff_records:
        is_active = (s.status == 1)  # 1: 已绑定在职, 0: 待绑定/待接受邀请
        is_owner = (s.role == ShopRole.OWNER.value or s.role == "owner")
        
        # 尝试安全地获取角色名称翻译
        try:
            role_name = ShopRole(s.role).label
        except Exception:
            role_name = "店长" if is_owner else "员工"
        
        # 🌟 核心逻辑：如果是待激活员工，自动生成专属加密 invite_token
        invite_token = None
        if not is_active:
            # 注意：这里的 staff_id 现在直接是 s.id (StaffModel的主键)
            invite_token = create_access_token(
                data={"shop_id": target_shop_id, "staff_id": s.id}
            )

        result_list.append({
            "id": s.id,                             # 单表结构，直接用 s.id
            "name": s.name or "员工",               # 也是直接取 s.name
            "is_active": is_active,
            "isActive": is_active,                  # 兼容驼峰与下划线命名
            "status": s.status,
            "isCreator": is_owner, 
            "roleName": role_name,
            "role": s.role,
            "invite_token": invite_token            # 🌟 Token 发送给前端，用于生成邀请码
        })

    # ---------------------------------------------------------
    # 4. 兜底数据（防止极端情况下空数据导致前端渲染崩溃）
    # ---------------------------------------------------------
    if not result_list:
        result_list = [{
            "id": current_user.id, # 兜底随便塞个ID防止前端报错
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
# 接口 2: 生成邀请 Token (点击邀请按钮时调用)declare
# ==========================================
@router.post("/staff/generate-invite")
def generate_invite(
    req: CreateInviteRequest,
    db: Session = Depends(get_db),
    current_admin: UserModel = Depends(get_current_user)
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
# 接口 3: 受邀员工接受邀请并绑定 OpenID (重构版：单表逻辑，彻底移除中间表)
# ==========================================
async def get_wx_openid_by_code(code: str) -> dict:
    """使用小程序临时 code 向微信 API 换取 openid 和 session_key"""
    appid = settings.WX_APP_ID
    secret = settings.WX_APP_SECRET

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": appid,
        "secret": secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        data = response.json()

    if "errcode" in data and data["errcode"] != 0:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信登录失败: {data.get('errmsg', '未知错误')}",
        )

    return data


@router.post("/accept-invite", summary="员工接受邀请并绑定微信")
async def accept_invite(
    req: AcceptInviteRequest,
    db: Session = Depends(get_db)
):
    target_shop_id = None
    target_staff_id = None

    # =========================================================
    # Step 1: 提取店铺与员工信息
    # =========================================================
    if req.invite_token:
        try:
            payload = jwt.decode(
                req.invite_token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[JWT_ALGORITHM]
            )
            target_staff_id = payload.get("staff_id")
            target_shop_id = payload.get("shop_id")
        except Exception:
            raise BusinessException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="邀请凭证已失效或不合法"
            )
            
    elif req.shop_id:
        target_shop_id = req.shop_id
        
    else:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="缺少邀请凭证或店铺信息"
        )

    # =========================================================
    # Step 2: 用 code 换取 OpenID 并查找/创建 UserModel
    # =========================================================
    wx_res = await get_wx_openid_by_code(req.code)
    openid = wx_res.get("openid")

    if not openid:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="微信登录凭证 (code) 无效"
        )

    user = db.query(UserModel).filter(UserModel.openid == openid).first()
    if not user:
        user = UserModel(openid=openid)
        db.add(user)
        db.flush()

    # =========================================================
    # Step 3: 严格查重逻辑与查找/新建 Staff 档案
    # =========================================================
    staff = None

    if target_staff_id:
        # -----------------------------------------------------
        # 【分支 A】指定店员邀请
        # -----------------------------------------------------
        # 1. 查询指定 ID 的 staff 档案
        staff = db.query(StaffModel).filter(
            StaffModel.id == target_staff_id,
            StaffModel.shop_id == target_shop_id
        ).first()

        if not staff:
            raise BusinessException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="未找到对应员工档案或已被移除"
            )

        # 🌟 查重 A1：检查该档案是否已被其他人绑定激活
        if staff.status == 1 and staff.user_id and staff.user_id != user.id:
            raise BusinessException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邀请已被其他人接受，无法重复领用"
            )

        # 🌟 查重 A2：检查当前微信用户是否在该店铺已有其他激活档案
        existing_user_staff = db.query(StaffModel).filter(
            StaffModel.shop_id == target_shop_id,
            StaffModel.user_id == user.id,
            StaffModel.status == 1,
            StaffModel.id != target_staff_id  # 排除当前记录
        ).first()

        if existing_user_staff:
            raise BusinessException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="您已经是该店铺的正式成员，无需重复认领其他档案"
            )

    else:
        # -----------------------------------------------------
        # 【分支 B】店铺通用邀请
        # -----------------------------------------------------
        # 🌟 查重 B1：检查当前微信用户在此店铺的档案状态
        staff = db.query(StaffModel).filter(
            StaffModel.shop_id == target_shop_id,
            StaffModel.user_id == user.id
        ).first()

        if staff:
            # 已存在且已激活
            if staff.status == 1:
                raise BusinessException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="您已经是该店铺的正式成员，无需重复加入"
                )
            # 已存在但为停用/禁用状态 (status == -1 或 0)
            # 可根据业务策略允许重新激活（逻辑在 Step 4 统一处理）
        else:
            # 首次加入，自动生成新店员记录
            staff = StaffModel(
                user_id=user.id,
                shop_id=target_shop_id,
                name=getattr(user, "nickname", None) or "新员工",
                role=ShopRole.STAFF.value,
                status=0
            )
            db.add(staff)
            db.flush()

    # =========================================================
    # Step 4: 激活员工状态
    # =========================================================
    try:
        staff.user_id = user.id
        staff.status = 1  # 标记为在职/正式激活
        
        db.commit()
        db.refresh(staff)
    except Exception as e:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"绑定失败: {str(e)}"
        )

    # =========================================================
    # Step 5: 签发 Access Token
    # =========================================================
    new_token = create_access_token(data={
        "sub": str(user.id),
        "staff_id": staff.id,
        "shop_id": staff.shop_id,
        "role": staff.role,
        "openid": user.openid
    })

    return {
        "token": new_token,
        "shop_id": staff.shop_id,
        "staff_id": staff.id,
        "role": staff.role,
        "nickname": staff.name,
        "message": "成功加入店铺！"
    }