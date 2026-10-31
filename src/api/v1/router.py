# src/api/v1/router.py
from fastapi import APIRouter

# 1. 集中導入所有業務模塊的 router
from src.api.v1.endpoints.clark_api import router as staff_router
from src.api.v1.endpoints.shop_api import router as shop_router
from src.api.v1.endpoints.default_identity_api import router as default_identity_router
from src.api.v1.endpoints.partner_api import router as partner_router
from src.api.v1.endpoints.inventory_api import router as inventory_router
from src.api.v1.endpoints.purchase_api import router as purchase_router
from src.api.v1.endpoints.dict_api import router as dict_router
from src.api.v1.endpoints.controller.config_routes import router as config_routes_router
from src.api.v1.endpoints.controller.execute_routes import router as execute_routes_router
from src.api.v1.endpoints.controller.vehicle_routes import router as vehicle_routes_router
from src.api.v1.endpoints.controller.scraper_projects import router as scraper_projects_router
from src.api.v1.endpoints.scraper_config_api import router as scraper_config_router
from src.modules.scraper.router import router as game_router
from src.api.v1.endpoints.test_proxy_api import router as test_proxy_router
from src.api.v1.endpoints.scraper_execution_api import router as scraper_execution_router
from src.api.v1.endpoints.test_step_request import router as test_step_router
from src.api.v1.endpoints.database_introspection import router as database_introspection_router
from src.api.v1.endpoints.controller.inventory import router as inventory_router

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

api_v1_router.include_router(
    dict_router,
    prefix="/dicts",
    tags=["字典管理"]
)

api_v1_router.include_router(
    config_routes_router,
    prefix="/vehicles",
    tags=["車輛数据抓取"]
)
api_v1_router.include_router(
    execute_routes_router,
    prefix="/vehicles",
    tags=["車輛数据抓取"]
)
# api_v1_router.include_router(
#     vehicle_routes_router,
#     prefix="/vehicles",
#     tags=["車輛数据抓取"]
# )

api_v1_router.include_router(
    scraper_config_router,
    prefix="/vehicles",
    tags=["車輛数据抓取"]
)

api_v1_router.include_router(
    game_router,
    prefix="/scraper",
    tags=["游戲数据抓取"]
)

api_v1_router.include_router(
    scraper_projects_router,
    prefix="/scraper_projects",
    tags=["爬蟲專案群組管理"]
)

api_v1_router.include_router(
    scraper_execution_router,
    prefix="",
    tags=["爬虫执行与预览"]
)

api_v1_router.include_router(
    test_proxy_router,
    prefix="",
    tags=["测试代理服务"]
)

api_v1_router.include_router(
    test_step_router,
    prefix="",
    tags=["测试步骤请求"]
)

api_v1_router.include_router(
    database_introspection_router,
    prefix="",
    tags=["数据库元数据查询"]
)

api_v1_router.include_router(
    inventory_router,
    prefix="",
    tags=["数据库元数据查询1"]
)

