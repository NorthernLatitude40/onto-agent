# 把json轉換成langgraph
from functools import partial
from typing import Any, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

# 加載 .env 文件中的 API Keys (安全保存在後端)
load_dotenv()

app = FastAPI()

# 允許前端 React 跨域訪問
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # 實際生產環境建議指定 React 的域名如 ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1. 定義 LangGraph 的全局狀態機數據結構 (State)
class AgentState(TypedDict):
    inputs: dict[str, Any]  # 初始輸入數據，例如 {"topic": "AI未來的發展"}
    outputs: dict[str, Any]  # 記錄各個節點的輸出結果
    history: list[dict[str, Any]]  # 執行歷史軌跡


# 2. 定義節點執行模板 (將來擴展新能力只需在這裡增加函數)
def run_start_node(state: AgentState, node_data: dict):
    print("--- 觸發起點節點 ---")
    # 把初始輸入直接帶入狀態中
    return {"outputs": {**state.get("outputs", {}), "current": "started"}}


def run_llm_node(state: AgentState, node_data: dict):
    print("--- 執行 LLM 節點 ---")
    # prompt_template = node_data.get("prompt", "")
    model_name = node_data.get("model", "default-model")

    # 簡單模擬變量替換 {{topic}} -> state["inputs"]["topic"]
    topic = state["inputs"].get("topic", "")
    # prompt = prompt_template.replace("{{topic}}", topic)

    # 這裡調用大模型 (實際開發時換成你的 LangChain / OpenAI Client)
    # api_key = os.getenv("DEEPSEEK_API_KEY") # 後端安全讀取
    ai_response = (
        f"【由 {model_name} 生成關於 {topic} 的文章】大模型思考後的完美回答..."
    )

    # 更新狀態機的 outputs 字典
    current_outputs = state.get("outputs", {})
    current_outputs["llm_result"] = ai_response

    return {"outputs": current_outputs}


def run_tool_search_node(state: AgentState, node_data: dict):
    print("--- 執行 搜尋工具 節點 ---")
    # 拿到上游 LLM 的結果作為搜尋關鍵字
    llm_result = state["outputs"].get("llm_result", "")

    # 模擬搜尋邏輯
    search_result = (
        f"針對【{llm_result[:10]}...】的 Google 搜尋結果：發現了3條相關新聞。"
    )

    current_outputs = state.get("outputs", {})
    current_outputs["search_result"] = search_result
    return {"outputs": current_outputs}


# 3. 核心：節點類型與執行函數的映射字典
NODE_MAP = {
    "start": run_start_node,
    "llm": run_llm_node,
    "tool_search": run_tool_search_node,
}


# 4. 接收前端 JSON 的 Pydantic 模型
class CanvasData(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    inputs: dict[str, Any]  # 用戶點擊執行時輸入的參數，例如 {"topic": "太空科技"}


# 5. FastAPI 接口：接收前端畫布數據，動態建圖並執行
@app.post("/api/workflow/run")
async def run_workflow(canvas: CanvasData):
    # 創建一個新的動態狀態圖
    workflow = StateGraph(AgentState)

    # A. 動態添加節點 (Nodes)
    for node in canvas.nodes:
        node_id = node["id"]
        node_type = node["type"]
        node_data = node.get("data", {})

        if node_type in NODE_MAP:
            # 使用 partial 預先注入前端配置的節點參數（如 prompt, model 等）
            node_func = partial(NODE_MAP[node_type], node_data=node_data)
            workflow.add_node(node_id, node_func)
        else:
            return {"status": "error", "message": f"未知的節點類型: {node_type}"}

    # B. 動態添加連線 (Edges)
    for edge in canvas.edges:
        source = edge["source"]
        target = edge["target"]
        workflow.add_edge(source, target)

    # C. 設定圖的起點與終點
    # 尋找前端傳過來的 start 節點作入口
    start_node_id = next((n["id"] for n in canvas.nodes if n["type"] == "start"), None)
    if not start_node_id:
        return {"status": "error", "message": "畫布中必須包含 start 節點"}

    workflow.set_entry_point(start_node_id)

    # 尋找沒有下游的節點，連向 END (或者簡單讓最後一個節點連向 END)
    # 這裡做個簡化處理：找到所有不是任何 edge 的 source 的節點，將它們連向 END
    sources = {edge["source"] for edge in canvas.edges}
    for node in canvas.nodes:
        if node["id"] not in sources and node["type"] != "start":
            workflow.add_edge(node["id"], END)

    # D. 編譯並運行 LangGraph
    compiled_app = workflow.compile()

    # 初始狀態
    initial_state = {"inputs": canvas.inputs, "outputs": {}, "history": []}

    # 執行圖
    final_output = compiled_app.invoke(initial_state)

    return {"status": "success", "result": final_output["outputs"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9090)
