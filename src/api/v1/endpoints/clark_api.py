from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from src.common.database import get_db
from src.model.staff_model import StaffModel
from src.model.clark_schema import StaffUpdateSchema, StaffResponse
from src.dependencies.permissions import allow_admin, allow_shop_manager, allow_shop_staff
from src.model.user_model import User

# 假設你有一個獲取當前請求用戶資訊的 Dependency
from src.api.auth_api import get_current_user 

router = APIRouter()

@router.put("/{staff_id}", response_model=StaffResponse, summary="統一更新員工資訊/狀態/角色")
def update_staff(
    staff_id: int,
    payload: StaffUpdateSchema,
    shop_id: Optional[int] = Header(None, alias="X-Shop-Id", description="當前選擇的店鋪ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(allow_shop_manager),
):
    target_shop_id = shop_id or getattr(current_user, "shop_id", 1)
    
    # 1. 查詢目標員工
    target_staff = db.query(StaffModel).filter(
        StaffModel.id == staff_id,
        StaffModel.shop_id == target_shop_id
    ).first()

    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="找不到該員工資訊"
        )

    # 2. 提取更新欄位 (Pydantic v2 建議使用 model_dump，若為 v1 可用 dict)
    update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)

    # 🌟 3. 角色變更邊界校驗 (完全不查庫，直接從 current_user 取出 Depends 已經查好的角色)
    if "role" in update_data:
        # Depends (allow_shop_manager) 裡面如果把 staff 資訊掛在 current_user 身上
        # 例如 current_user.current_staff.role 或 current_user.role
        operator_role = getattr(current_user, "role", None)
        if hasattr(current_user, "current_staff") and current_user.current_staff:
            operator_role = current_user.current_staff.role

        # 越權保護：只有店長 (manager) 嘗試動 Owner 權限時攔截；Owner 或其它通過 Depend 的角色直接放行
        if operator_role == "manager":
            if target_staff.role == "owner" or update_data["role"] == "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="權限不足：店長(manager)無法變更店主的角色"
                )

    # 4. 執行更新邏輯
    for field, value in update_data.items():
        setattr(target_staff, field, value)

    db.commit()
    db.refresh(target_staff)
    return StaffResponse(
        id=target_staff.id,
        nickname=target_staff.name,
        role=target_staff.role,
        status=target_staff.status,
        is_active=False
    )