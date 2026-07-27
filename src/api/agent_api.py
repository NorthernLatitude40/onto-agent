# api/agent_api.py
import json
import logging
import os
import traceback
import uuid
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import APIRouter, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware  # 💡 導入 CORS 中間件
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("API_SERVICE")


# 1. 定義標準的請求載荷（Payload）
class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None  # 允許外部傳入自訂的會話 ID，用於辨識不同用戶


# 4. 工廠函數：創立 FastAPI 實例並注入全局 harness
global_harness = None


# 🌟 新增：2. 健康檢查接口 (Health Check)
# 運維系統、Docker 或 K8s 可以定時調用這個接口確保服務活著
@router.get("/health", summary="檢查系統健康狀態")
async def health_check():
    # 這裡未來可以擴展加入：檢查 Neo4j 连通性、檢查 MCP 是否掛載等
    return {"status": "healthy", "service": "OntoAgent Core Engine", "version": "1.0.0"}


def sse_event(data: dict) -> str:
    """統一構造 SSE 格式字符串，避免多行 f-string 嵌套 dict 造成的語法/可讀性問題"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# 🌟 升級：3. 流式對話接口 (Streaming Chat)
@router.post("/chat", summary="Agent 流式推理對話")
async def agent_api_endpoint(payload: ChatPayload):
    # 多租戶/多用戶隔離邏輯
    current_thread_id = payload.session_id or f"api_session_{uuid.uuid4().hex[:8]}"

    logger.info(
        f"[/chat] 新請求 thread_id={current_thread_id} message={payload.message!r}"
    )

    async def event_generator():
        try:
            # 狀態事件
            yield sse_event(
                {
                    "type": "status",
                    "content": "OntoAgent 收到請求，正在啟動推理工作流...",
                }
            )

            # 真正流式輸出
            async for token in global_harness.interact_stream(
                user_message=payload.message,
                thread_id=current_thread_id,
            ):
                if not token:
                    continue
                yield sse_event({"type": "token", "content": token})

            # 推理結束
            yield sse_event({"type": "done"})
            logger.info(f"[/chat] thread_id={current_thread_id} 推理完成")

        except (ImportError, Exception) as e:
            # 關鍵修正：異常必須先完整記錄到服務端日誌（含完整 traceback），
            # 之前的版本只把 str(e) 發給前端，服務端終端永遠看不到堆疊。
            logger.error(
                f"[/chat] thread_id={current_thread_id} 發生異常: {e}\n"
                f"{traceback.format_exc()}"
            )

            yield sse_event({"type": "error", "content": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

UPLOAD_DIR = "/home/ww/projects/langgraph_workspace/uploads"

# 1. 專門處理檔案上傳的接口 (0 Token)
@router.post("/upload")
async def upload_code(file: Annotated[UploadFile, File()]):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as buffer:
        buffer.write(content)
        
    return {
        "status": "success",
        "file_path": file_path  # 回傳路徑給前端，後續對話可引用
    }

@router.post("/workflow/run")
async def deploy_canvas(graph_dto: dict):
    """
    接收前端畫布發送過來的完整 JSON 數據
    """
    # 這裡的 graph_dto 就是前端畫布的 JSON
    print("【前端畫布傳來的原始數據】:", graph_dto)
    # 傳入 JSON 進行動態編譯
    global_harness.agent_core.deploy_or_update_flow(
        ui_graph_json=graph_dto,
        tools_list=global_harness.agent_core.tool_node,
        model=global_harness.agent_core._model(),
    )

    return {"status": "success", "message": "畫布編譯並部署成功！"}


def create_api(harness) -> FastAPI:
    """
    【Harness API 接入組件】
    完全依賴注入 Harness 實例，內部不再有任何 LangGraph 的字典解包邏輯。
    """
    global global_harness
    global_harness = harness  # 鎖定全局變量供路由使用

    app = FastAPI(title="Agent Harness API Gateway")
    # 💡 定義允許訪問的前端來源列表
    origins = [
        "http://localhost:5173",  # 你的 Vite 前端地址
        "http://127.0.0.1:5173",
        # 如果未來有其他前端地址，也可以加在這裡
    ]
    # 💡 將 CORS 中間件加入到 FastAPI 實例中
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # 允許的來源列表
        allow_credentials=True,  # 允許攜帶 Cookie / 認證資訊
        allow_methods=["*"],  # 允許所有的請求方法 (POST, GET, OPTIONS 等)
        allow_headers=["*"],  # 允許所有的請求標頭 (Content-Type, Authorization 等)
    )

    # 1. 取得當前執行文件 (main.py) 的目錄絕對路徑
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # 2. 定義 exports 目錄的絕對路徑
    EXPORTS_DIR = BASE_DIR / "exports"

    # 3. 確保目錄存在
    if not EXPORTS_DIR.exists():
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- 打印日誌 ---
    print("=" * 50)
    print("🚀 伺服器啟動配置:")
    print(f"📂 檔案存放目錄 (Absolute Path): {EXPORTS_DIR}")
    print("🌐 靜態文件掛載點 (URL Path): /files")
    print(f"✅ 檢查目錄狀態: {'存在' if EXPORTS_DIR.exists() else '不存在'}")
    print("=" * 50)
    # ----------------

    # 4. 使用絕對路徑進行掛載
    app.mount("/files", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

    app.include_router(router)

    return app
