import uvicorn
import logging
from src.core.harness import AgentHarness
from src.api.agent_api import create_api

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # 確保輸出到終端，Docker logs 才看得到
)
logger = logging.getLogger("API_SERVICE")


def run_api():
    logger.info("🚀 [FastAPI] 服務開始初始化...")

    try:
        worker = AgentHarness()
        logger.info("🛠️ [FastAPI] AgentHarness 正在 bootstrap...")
        worker.bootstrap()

        api_app = create_api(worker)
        logger.info("✅ [FastAPI] API 建立成功，準備啟動 Uvicorn...")

        # 啟動 Uvicorn
        uvicorn.run(
            api_app,
            host="0.0.0.0",
            port=8000,
            log_level="info",  # 設為 info 可以看到更多啟動細節
            access_log=True,  # 顯示請求日誌
        )
    except Exception as e:
        logger.error(f"❌ [FastAPI] 啟動失敗: {e}", exc_info=True)
        raise e


if __name__ == "__main__":
    run_api()
