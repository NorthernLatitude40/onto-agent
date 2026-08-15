from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.model.clark_schema import SetDefaultIdentityResponse, SetDefaultIdentitySchema
from src.api.auth_api import get_current_user, create_access_token
from src.model.user_model import UserModel
from src.common.database import get_db
from src.model.staff_model import StaffModel

router = APIRouter()

@router.put(
    "/default-identity", 
    response_model=SetDefaultIdentityResponse,
    summary="设置用户的全局默认店铺及身份"
)
def set_default_identity(
    payload: SetDefaultIdentitySchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # 1. 安全校验：验证提交的 staff_id 是否真的属于当前用户，且属于指定的 shop_id
    staff = db.query(StaffModel).filter(
        StaffModel.id == payload.default_staff_id,
        StaffModel.user_id == current_user.id,
        StaffModel.shop_id == payload.default_shop_id,
        StaffModel.status == 1  # 在职状态
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指定的店铺身份无效或不属于当前用户"
        )

    # 2. 更新数据库 sys_user 表
    current_user.default_shop_id = payload.default_shop_id
    current_user.default_staff_id = payload.default_staff_id

    try:
        db.add(current_user)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库更新失败: {str(e)}"
        )

    # 3. 仅返回简单的成功提示，不触发个人资料等 UI 数据的重绘
    return SetDefaultIdentityResponse(
        code=200,
        message="默认身份设置成功"
    )