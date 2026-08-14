import json
import logging
import os
import traceback
import uuid
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import APIRouter, FastAPI, File, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from src.common.exceptions import BusinessException, register_exception_handlers
from src.core.shop_agent.system import ShopAgentSystem
from src.config.config import settings



router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("API_SERVICE")

shop_agent = ShopAgentSystem()

# ----------------------------------------------------------------------
# Dependencies & Helpers
# ----------------------------------------------------------------------
def get_harness(request: Request):
    """【依赖注入】从 app.state 获取 AgentHarness，避免全局变量污染"""
    harness = getattr(request.app.state, "worker", None)
    if not harness:
        raise BusinessException(
            detail="Agent Harness 未初始化", 
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return harness


def sse_event(data: dict) -> str:
    """构建标准 SSE 事件格式"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------
class ChatPayload(BaseModel):
    message: str = Field(..., description="用户输入的对话文本")
    session_id: str | None = Field(default=None, description="会话ID，留空自动生成")


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@router.get("/health", summary="检查系统健康状态")
async def health_check():
    return {
        "status": "healthy",
        "service": "OntoAgent Core Engine",
        "version": "1.0.0"
    }


@router.post("/chat", summary="Agent 流式推理对话")
async def agent_api_endpoint(
    payload: ChatPayload,
    request: Request,
):
    harness = get_harness(request)
    current_thread_id = payload.session_id or f"api_session_{uuid.uuid4().hex[:8]}"

    logger.info(f"[/chat] 新请求 thread_id={current_thread_id} message={payload.message!r}")

    async def event_generator():
        try:
            # 1. 状态事件
            yield sse_event({
                "type": "status",
                "content": "OntoAgent 收到请求，正在启动推理工作流..."
            })

            # 2. 流式输出 Token
            async for token in harness.interact_stream(
                user_message=payload.message,
                thread_id=current_thread_id,
            ):
                if token:
                    yield sse_event({"type": "token", "content": token})

            # 3. 结束标识
            yield sse_event({"type": "done"})
            logger.info(f"[/chat] thread_id={current_thread_id} 推理完成")

        except Exception as e:
            logger.error(
                f"[/chat] thread_id={current_thread_id} 发生异常: {e}\n{traceback.format_exc()}"
            )
            # SSE 内部报错，推送标准的 error 事件给前端
            yield sse_event({
                "type": "error",
                "code": 500,
                "content": "Agent 推理过程发生错误，请稍后重试"
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓存，确保流式实时性
        }
    )


@router.post("/upload", summary="上传代码/文件")
async def upload_code(file: Annotated[UploadFile, File()]):
    if not file.filename:
        raise BusinessException(detail="未传入有效文件名", status_code=400)

    # 安全性防范：清理文件名，防止路径穿越攻击（Path Traversal）
    safe_filename = Path(file.filename).name
    file_path = settings.UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe_filename}"

    try:
        content = await file.read()
        async with aiofiles.open(file_path, "wb") as buffer:
            await buffer.write(content)
    except Exception as e:
        logger.error(f"文件写入失败: {e}", exc_info=True)
        raise BusinessException(detail="文件保存失败", status_code=500)

    return {
        "code": 200,
        "message": "文件上传成功",
        "data": {
            "filename": safe_filename,
            "file_path": str(file_path),
        }
    }


@router.post("/workflow/run", summary="部署并编译前端画布 JSON")
async def deploy_canvas(graph_dto: dict, request: Request):
    harness = get_harness(request)
    logger.info("【收到前端画布部署请求】")

    try:
        harness.agent_core.deploy_or_update_flow(
            ui_graph_json=graph_dto,
            tools_list=harness.agent_core.tool_node,
            model=harness.agent_core._model(),
        )
    except Exception as e:
        logger.error(f"画布编译部署失败: {e}", exc_info=True)
        raise BusinessException(detail=f"画布编译部署失败: {str(e)}", status_code=400)

    return {"code": 200, "message": "画布编译并部署成功！", "data": None}


