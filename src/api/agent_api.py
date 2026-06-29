# api/agent_api.py
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from typing import Optional
import asyncio
from fastapi.responses import StreamingResponse
import uuid
from fastapi.middleware.cors import CORSMiddleware  # 💡 導入 CORS 中間件

router = APIRouter(prefix="/api/v1")


# 1. 定義標準的請求載荷（Payload）
class ChatPayload(BaseModel):
    message: str
    session_id: Optional[str] = None  # 允許外部傳入自訂的會話 ID，用於辨識不同用戶


# 4. 工廠函數：創立 FastAPI 實例並注入全局 harness
global_harness = None


# 🌟 新增：2. 健康檢查接口 (Health Check)
# 運維系統、Docker 或 K8s 可以定時調用這個接口確保服務活著
@router.get("/health", summary="檢查系統健康狀態")
async def health_check():
    # 這裡未來可以擴展加入：檢查 Neo4j 连通性、檢查 MCP 是否掛載等
    return {"status": "healthy", "service": "OntoAgent Core Engine", "version": "1.0.0"}


# 🌟 升級：3. 流式對話接口 (Streaming Chat)
@router.post("/chat", summary="Agent 流式推理對話")
async def agent_api_endpoint(payload: ChatPayload):
    # 多租戶/多用戶隔離邏輯
    current_thread_id = payload.session_id or f"api_session_{uuid.uuid4().hex[:8]}"

    # 這裡我們定義一個生成器函數 (Generator)，用來逐字/逐個事件往外吐數據
    async def event_generator():
        try:
            # 💡 這裡對接你的 LangGraph 工作流的 stream 方法
            # 假設你的 harness 裡面有一個支持 stream 的方法，例如 harness.stream_interact
            # 如果目前只有同步的 interact，可以用下面這個模擬流式的效果（或者直接對接 LangGraph 的 stream）

            # ── 這裡以標準的 LangGraph 異步流式為例 ──
            # config = {"configurable": {"thread_id": current_thread_id}}
            # async for event in google_harness.agent.astream({"messages": [("user", payload.message)]}, config):
            #     yield f"data: {event}\n\n"

            # 1. 提示客戶端：後端已經收到請求，正在調度 LangGraph
            yield f"data: [STATUS] OntoAgent 收到請求，正在啟動推理工作流...\n\n"

            # 2. 🌟 真正的真流式：LLM 吐一個字，這裡就包裝成標準 SSE 格式 yield 一個字！
            async for token in global_harness.interact_stream(
                user_message=payload.message, thread_id=current_thread_id
            ):
                if token:  # 確保 token 不為空
                    # ⚠️ 每一段輸出的字，都必須用 data: {token}\n\n 包裹起來
                    yield f"data: {token}\n\n"

        except Exception as e:
            yield f"data: [ERROR] 內部分析出錯: {str(e)}\n\n"

    # 使用 FastAPI 內置的 StreamingResponse 返回，媒體類型聲明為 text/event-stream (SSE協議)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
    app.include_router(router)

    return app
