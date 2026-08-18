# src/api/v1/router.py
from fastapi import APIRouter

# 1. 集中導入所有業務模塊的 router
from src.api.v1.endpoints.clark_api import router as staff_router
from src.api.v1.endpoints.shop_api import router as shop_router
from src.api.v1.endpoints.default_identity_api import router as default_identity_router
from src.api.v1.endpoints.partner_api import router as partner_router
from src.api.v1.endpoints.inventory_api import router as inventory_router
from src.api.v1.endpoints.purchase_api import router as purchase_router

# 2. 創建 V1 版本的 API 總路由
api_v1_router = APIRouter(prefix="/api/v1")

# 3. 統一管理與註冊各個模塊 (路徑、標籤一目了然)
api_v1_router.include_router(
    staff_router, 
    prefix="/shop/staffs", 
    tags=["1. 店鋪員工管理"]
)

api_v1_router.include_router(
    shop_router, 
    prefix="/shops", 
    tags=["2. 店鋪管理"]
)

api_v1_router.include_router(
    default_identity_router, 
    prefix="/user", 
    tags=["用户配置"]
)

api_v1_router.include_router(
    partner_router,  
    prefix="/partners",
    tags=["往來單位管理"]
)

api_v1_router.include_router(
    inventory_router,  
    prefix="/inventories",
    tags=["庫存管理"]
)

api_v1_router.include_router(
    purchase_router,  
    prefix="/purchases",
    tags=["採購管理"]
)