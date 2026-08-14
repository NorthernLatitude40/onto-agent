import time
import httpx
import jwt
from datetime import datetime, date, time as dt_time
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy.exc import IntegrityError

from src.common.database import get_db
from src.model.staff_model import StaffModel
from src.model.clark_schema import StaffUpdateSchema, StaffResponse
from src.dependencies.permissions import allow_admin, allow_shop_manager, allow_shop_staff
from src.model.user_model import User
from src.config.config import settings
from src.common.dict import SystemRole, ShopRole
from src.api.auth_api import get_current_user, create_access_token
from src.model.schema import  CreateInviteRequest, AcceptInviteRequest, CreateStaffRequest
from src.common.exceptions import BusinessException
from src.common.constants import TOKEN_EXPIRE_HOURS, JWT_ALGORITHM
from src.common.i18n import ErrorCode, get_i18n_message
from src.model.shop_staff_model import ShopStaffModel

# 假設你有一個獲取當前請求用戶資訊的 Dependency
from src.api.auth_api import get_current_user 

router = APIRouter()

# ==========================================
# 接口 1: 管理员新增员工档案 (未绑定 openid)
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

    # ---------------------------------------------------------
    # 2. 🛡️ 重名校验：精准限制在【当前店铺】范围内查重
    # ---------------------------------------------------------
    # 🌟 关键修复：status 字段属于 ShopStaffModel，使用 ShopStaffModel.status 过滤
    existing_relation = db.query(ShopStaffModel).join(
        StaffModel, ShopStaffModel.staff_id == StaffModel.id
    ).filter(
        ShopStaffModel.shop_id == shop_id,
        StaffModel.name == req.nickname,
        ShopStaffModel.status.in_([0, 1])  # 0: 待认领, 1: 正常在职 (过滤掉 2: 已离职/禁用)
    ).first()

    if existing_relation:
        status_text = "待接受邀请" if existing_relation.status == 0 else "在职"
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"店铺内已存在名为 '{req.nickname}' 的{status_text}员工，请勿重复创建"
        )

    # ---------------------------------------------------------
    # 3. 核心业务：预创建员工档案（绑定从 Header 传进来的 shop_id）
    # ---------------------------------------------------------
    # 获取角色字符串 (兼容 Enum 枚举和纯字符串)
    staff_role = req.role.value if hasattr(req.role, 'value') else req.role

    try:
        # 步骤 1：创建员工个人档案 (表 1: staff)
        new_staff = StaffModel(
            user_id=None,                 # 未接受邀请前为 None
            name=req.nickname             # 员工姓名/备注
        )
        db.add(new_staff)
        db.flush()  # 💡 刷新事务，提前获取 new_staff.id

        # 步骤 2：创建店铺与员工的绑定关系 (表 2: shop_staff)
        new_shop_staff_relation = ShopStaffModel(
            shop_id=shop_id,              # 从 Header 传进来的 shop_id
            staff_id=new_staff.id,        # 关联刚刚创建的 staff.id
            role=staff_role,              # 员工在该店的角色
            status=0                      # 0: 待认领/待接受邀请
        )
        db.add(new_shop_staff_relation)

        # 步骤 3：一次性提交事务 (保证原子性)
        db.commit()
        db.refresh(new_staff)
        db.refresh(new_shop_staff_relation)

    except IntegrityError:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="创建失败，员工数据或关联重复"
        )
    except Exception as e:
        db.rollback()
        raise BusinessException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"系统异常，创建员工失败: {str(e)}"
        )

    # ---------------------------------------------------------
    # 4. Bare Payload 模式返回规范 Response
    # ---------------------------------------------------------
    return StaffResponse(
        id=new_staff.id,
        nickname=new_staff.name,
        role=new_shop_staff_relation.role,
        status=new_shop_staff_relation.status,
        is_active=False
    )

@router.put("/{staff_id}", response_model=StaffResponse, summary="統一更新員工資訊/狀態/角色")
def update_staff(
    staff_id: int,
    payload: StaffUpdateSchema,
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="當前選擇的店鋪ID"),
    db: Session = Depends(get_db),
    current_user: StaffModel = Depends(allow_shop_manager),
):
    # 0. 確定當前操作的店鋪 ID
    target_shop_id = shop_id or getattr(current_user, "current_shop_id", 1)

    # 1. 查詢【目標員工】的基本資料 (StaffModel)
    target_staff = db.query(StaffModel).filter(StaffModel.id == staff_id).first()
    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="找不到該員工基本資訊"
        )

    # 2. 查詢【目標員工】在【當前店鋪】的關聯紀錄 (ShopStaffModel)
    target_relation = db.query(ShopStaffModel).filter(
        ShopStaffModel.staff_id == staff_id,
        ShopStaffModel.shop_id == target_shop_id
    ).first()

    if not target_relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="該員工不屬於當前店鋪"
        )

    # 3. 提取前端傳進來的有效更新欄位 (過濾掉未傳遞的 None)
    update_data = payload.model_dump(exclude_unset=True, mode="json") if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True, use_enum_values=True)

    # 🌟 4. 越權保護：查詢【操作者自己】在當前店鋪的角色
    operator_relation = db.query(ShopStaffModel).filter(
        ShopStaffModel.staff_id == current_user.id,
        ShopStaffModel.shop_id == target_shop_id
    ).first()
    
    operator_role = operator_relation.role if operator_relation else None

    # 如果嘗試變更角色，進行越權保護校驗
    if "role" in update_data:
        new_role = update_data["role"]
        # 店長 (manager) 不能修改店主 (owner) 的角色，也不能將別人提升為店主 (owner)
        if operator_role == "manager":
            if target_relation.role == "owner" or new_role == "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="權限不足：店長(manager)無法變更店主(owner)的角色"
                )

    # 🌟 5. 數據更新分流處理（核心修復！）

    # A. 更新 StaffModel 屬於個人的欄位 (例如: name, phone 等)
    staff_fields = {"name", "phone", "avatar", "nickname"}
    for field in staff_fields:
        if field in update_data and update_data[field] is not None:
            setattr(target_staff, field, update_data[field])

    # B. 更新 ShopStaffModel 屬於店鋪關聯的欄位 (role, status)
    if "role" in update_data and update_data["role"] is not None:
        # 如果 update_data["role"] 是 Enum 物件，轉成 value
        role_val = update_data["role"]
        target_relation.role = role_val.value if hasattr(role_val, "value") else str(role_val)

    if "status" in update_data and update_data["status"] is not None:
        target_relation.status = update_data["status"]

    # 6. 統一提交資料庫更新
    db.add(target_staff)
    db.add(target_relation)
    db.commit()
    
    db.refresh(target_staff)
    db.refresh(target_relation)

    # 7. 組裝回傳
    return StaffResponse(
        id=target_staff.id,
        nickname=target_staff.name,
        role=target_relation.role,
        status=target_relation.status,
        is_active=(target_relation.status == 1)
    )

# ──────── 🌟 2：查询店铺下所有关联员工 ────────
@router.get("", summary="查询店铺下关联的所有员工")
def get_staff_list(
    x_shop_id: int = Header(..., alias="X-Shop-Id"),
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
    staff_relation = db.query(ShopStaffModel).filter(
        ShopStaffModel.shop_id == x_shop_id,
        ShopStaffModel.staff_id == current_user.id
    ).first()
    
    if not staff_relation:
        raise BusinessException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权管理该店铺的员工档案"
        )
    target_shop_id = x_shop_id

    if is_super_admin:
        if is_production:
            # 🛑 生产线上环境：严禁超管越权穿透，直接抛出权限异常或限制只能看自己的
            if x_shop_id and x_shop_id != target_shop_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="线上生产环境禁止超级管理员越权跨店查看客户员工数据！"
                )
        else:
            # 🟢 开发/测试环境：允许超管自由穿透传入 shop_id 测试
            if x_shop_id:
                target_shop_id = x_shop_id
    else:
        # 普通店员/店长：强行限制只能查自己所在店铺
        if x_shop_id and x_shop_id != target_shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权查看非本店铺的员工信息！"
            )

    # 2. 从数据库 StaffModel (staff) 表检索员工
    staff_records = db.query(ShopStaffModel).filter(
        ShopStaffModel.shop_id == target_shop_id
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
                data={"shop_id": target_shop_id, "staff_id": s.staff_id}
            )

        result_list.append({
            "id": s.staff.id,                             # staff 档案 ID
            "name": s.staff.name or "员工",
            "is_active": is_active,
            "isActive": is_active,                # 兼容驼峰与下划线命名
            "status": s.status,
            "isCreator": is_owner, 
            "roleName": ShopRole(s.role).label,
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
# 接口 2: 生成邀请 Token (点击邀请按钮时调用)
# ==========================================
@router.post("/staff/generate-invite")
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
# 接口 3: 受邀员工接受邀请并绑定 OpenID, 大部分时候邀请时还未注册
# ==========================================
async def get_wx_openid_by_code(code: str) -> dict:
    """使用小程序临时 code 向微信 API 换取 openid 和 session_key"""
    # 从你的 settings/env 获取小程序的 AppID 和 AppSecret
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

    # 微信接口返回 errcode 不为 0 表示报错
    if "errcode" in data and data["errcode"] != 0:
        raise BusinessException(
            status_code=400,
            detail=f"微信登录失败: {data.get('errmsg', '未知错误')}",
        )

    return data  # 返回格式如: {"openid": "xxx", "session_key": "xxx"}

@router.post("/accept-invite")
async def accept_invite(
    req: AcceptInviteRequest,
    db: Session = Depends(get_db)
):
    target_shop_id = None
    target_staff_id = None

    # ---------------------------------------------------------
    # Step 1: 解析邀請憑證 (模式 A: token / 模式 B: shop_id)
    # ---------------------------------------------------------
    if req.invite_token:
        try:
            payload = jwt.decode(
                req.invite_token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
            )
            target_staff_id = payload.get("staff_id")
            target_shop_id = payload.get("shop_id")
        except Exception:
            raise BusinessException(status_code=400, detail="無效的邀請連結")
            
        # 驗證該專屬邀請記錄是否存在
        shop_staff = db.query(ShopStaffModel).filter(
            ShopStaffModel.staff_id == target_staff_id,
            ShopStaffModel.shop_id == target_shop_id
        ).first()

        if not shop_staff:
            raise BusinessException(status_code=404, detail="邀請資訊已失效或不存在")

    elif req.shop_id:
        target_shop_id = req.shop_id
    else:
        raise BusinessException(status_code=400, detail="缺少邀請憑證或店鋪ID")

    # ---------------------------------------------------------
    # Step 2: 用 code 換取微信 openid
    # ---------------------------------------------------------
    wx_res = await get_wx_openid_by_code(req.code)
    openid = wx_res.get("openid")

    if not openid:
        raise BusinessException(status_code=400, detail="微信登入憑證無效")

    # ---------------------------------------------------------
    # Step 3: 查找或自動註冊 User & Staff 基礎檔案
    # ---------------------------------------------------------
    user = db.query(User).filter(User.openid == openid).first()

    if not user:
        user = User(openid=openid, role=SystemRole.MERCHANT)
        db.add(user)
        db.flush()

    # 獲取或懶加載建立 StaffProfile
    staff_profile = db.query(StaffModel).filter(StaffModel.user_id == user.id).first()
    if not staff_profile:
        staff_profile = StaffModel(
            user_id=user.id,
            name=f"店員_{user.id}"
        )
        db.add(staff_profile)
        db.flush()

    # ---------------------------------------------------------
    # Step 4: 關鍵防禦 - 檢查是否已經是該店鋪成員
    # ---------------------------------------------------------
    already_member = db.query(ShopStaffModel).filter(
        ShopStaffModel.shop_id == target_shop_id,
        ShopStaffModel.staff_id == staff_profile.id
    ).first()

    if already_member and already_member.status == 1:
        raise BusinessException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.USER_ALREADY_MEMBER,
            detail="您已經是該店鋪的成員，請勿重複加入"
        )

    # ---------------------------------------------------------
    # Step 5: 綁定店鋪關聯 (ShopStaffModel)
    # ---------------------------------------------------------
    if not already_member:
        already_member = ShopStaffModel(
            shop_id=target_shop_id,
            staff_id=staff_profile.id,
            role="staff",
            status=1
        )
        db.add(already_member)
    else:
        already_member.status = 1  # 激活狀態

    db.commit()

    # ---------------------------------------------------------
    # Step 6: 簽發新 Token 並回傳
    # ---------------------------------------------------------
    new_token = create_access_token(data={
        "sub": str(user.id),
        "role": already_member.role,
        "openid": user.openid
    })

    return {
        "token": new_token,
        "shop_id": target_shop_id,
        "staff_id": staff_profile.id,
        "role": already_member.role,
        "message": "成功加入店鋪！"
    }