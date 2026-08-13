import os
import sys
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.common.logger import setup_logging, get_logger
from fastapi.staticfiles import StaticFiles
from src.common.exceptions import BusinessException, register_exception_handlers
from fastapi.middleware.cors import CORSMiddleware
from src.config.config import settings
from src.api.v1.router import api_v1_router

# ⚙️ 1. 初始化全局统一日志（只在入口调用一次）
setup_logging()

# ⚙️ 2. 获取当前模块的 logger
logger = get_logger("API_SERVICE")

def run_api():
    logger.info("🚀 [FastAPI] 准备启动 Uvicorn 服务...")

    # 从环境变量读取配置，设置合理默认值
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    # 生产环境控制：生产环境建议设置为 False
    is_debug = os.getenv("ENV", "production").lower() == "development"
    
    # 动态获取 CPU 核心数/进程数（Render 等平台默认为 1，可由环境变量覆盖）
    workers = int(os.getenv("WEB_CONCURRENCY", 1))

    logger.info(f"🌐 绑定地址: http://{host}:{port} | 进程数(Workers): {workers} | Debug: {is_debug}")

    try:
        # 💡 最佳实践：使用 "模块路径:工厂函数" 字符串形式传入 app
        # 这样 Uvicorn 才能在 workers > 1 时正常多进程 fork
        uvicorn.run(
            "src.api.agent_server:create_app",  # 假设本文件路径为 src/main.py，请根据实际入口路径调整
            factory=True,
            host=host,
            port=port,
            reload=is_debug,        # 开发模式下开启热重载
            workers=workers if not is_debug else 1,
            log_level="info",
            access_log=True,
            proxy_headers=True,     # ⚡ 关键：在 Render/Nginx 反向代理后，正确获取客户端真实 IP
            forwarded_allow_ips="*",
        )
    except Exception as e:
        logger.critical(f"💥 [FastAPI] Uvicorn 遭遇致命崩溃: {e}", exc_info=True)
        sys.exit(1)


# ----------------------------------------------------------------------
# 生命周期管理与 App 工厂函数 (用于配合 Uvicorn factory=True)
# ----------------------------------------------------------------------
def create_app() -> FastAPI:
    """
    App 工厂函数，将 AgentHarness 的初始化延迟到真正的 FastAPI lifespan 周期中，
    保障平滑启动与优雅停机（Graceful Shutdown）。
    """
    from src.core.harness import AgentHarness

    # 初始化 Worker 实例
    worker = AgentHarness()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 🟢【Startup 阶段】：应用启动时触发
        logger.info("🛠️ [Lifespan] AgentHarness 开始执行 bootstrap 流程...")
        try:
            worker.bootstrap()
            logger.info("✅ [Lifespan] AgentHarness 引导完成！")
        except Exception as e:
            logger.error(f"❌ [Lifespan] Harness 启动失败: {e}", exc_info=True)
            raise e
        
        yield  # 对应服务运行期间

        # 🔴【Shutdown 阶段】：收到关闭信号（SIGTERM/SIGINT）时触发
        logger.info("🛑 [Lifespan] 接收到停机信号，开始清理资源...")
        if hasattr(worker, "shutdown") and callable(worker.shutdown):
            await worker.shutdown() if asyncio.iscoroutinefunction(worker.shutdown) else worker.shutdown()
        logger.info("👋 [Lifespan] 资源释放完毕，服务优雅退出。")

    # 构建并注册 lifespan
    app = create_api(harness=worker)
    app.router.lifespan_context = lifespan

    return app

# ----------------------------------------------------------------------
# 工厂函数 (App Creator)
# ----------------------------------------------------------------------
def create_api(harness) -> FastAPI:
    app = FastAPI(title="Agent Harness API Gateway")

    # 1. 挂载全局 Harness 实例到 state，供 Depends 读取
    app.state.worker = harness

    # 2. 注册全局异常处理器
    register_exception_handlers(app)

    # 3. 动态配置 CORS 中间件（支持环境变量覆盖）
    allowed_origins = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 确保必要的目录存在
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 4. 挂载静态文件导出目录
    app.mount("/files", StaticFiles(directory=str(settings.EXPORTS_DIR)), name="exports")

    # 5. 挂载各模块路由
    from src.api.auth_api import router as auth_router
    from src.api.dashboard_api import dashboard_router, shop_router
    from src.api.agent_api import router

    app.include_router(router)
    app.include_router(api_v1_router)
    app.include_router(dashboard_router)
    app.include_router(shop_router)
    app.include_router(auth_router)

    logger.info("✅ Agent Harness API Gateway 挂载完成")
    return app


if __name__ == "__main__":
    run_api()