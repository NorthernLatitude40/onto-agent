import os
import sys
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.common.logger import setup_logging, get_logger

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
    from src.api.agent_api import create_api
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


if __name__ == "__main__":
    run_api()