# api/agent_api.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import uuid

# 1. 定義標準的請求載荷（Payload）
class ChatPayload(BaseModel):
    message: str
    session_id: Optional[str] = None  # 允許外部傳入自訂的會話 ID，用於辨識不同用戶

def create_api(harness) -> FastAPI:
    """
    【Harness API 接入組件】
    完全依賴注入 Harness 實例，內部不再有任何 LangGraph 的字典解包邏輯。
    """
    app = FastAPI(title="Agent Harness API Gateway")

    @app.post("/agent")
    def agent_api_endpoint(payload: ChatPayload):
        user_query = payload.message
        
        # 2. 多租戶/多用戶隔離核心邏輯：
        # 如果調用方傳了 session_id（例如：用户ID_商品ID），就用他的；
        # 如果沒傳，就動態生成一個 uuid，確保各個 API 請求的記憶互不干擾！
        current_thread_id = payload.session_id or f"api_session_{uuid.uuid4().hex[:8]}"
        
        # 3. 🌟 呼叫 Harness 的極簡一體化接口
        final_reply = harness.interact(
            user_message=user_query, 
            thread_id=current_thread_id
        )
        
        # 4. 返回乾淨的 JSON，並把當前使用的 session_id 回傳給前端，方便下次帶上
        return {
            "output": final_reply,
            "session_id": current_thread_id
        }

    return app