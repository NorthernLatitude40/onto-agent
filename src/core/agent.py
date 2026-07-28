import os
import re
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src.core.llm_router import router
from src.core.prompts import AGENT_SYSTEM_PROMPT, DESIGNER_SYSTEM_PROMPT, TESTER_SYSTEM_PROMPT
from src.core.tools.generate_design_doc import (
    generate_design_doc,
)
from src.core.tools.tools import (
    generate_excel,
    get_weather,
    search_official_knowledge_base,
    validate_design_json,
)
from src.core.workflow import DynamicGraphCompiler

# import atexit
# atexit.register(self.langfuse.flush)

FILE_PATH_PATTERN = re.compile(r'[/\w\-\.]+\.(tsx|jsx|py|ts|js)\b')


class State(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str


class RouterParseError(Exception):
    """Router LLM 輸出無法解析出合法意圖時拋出"""
    pass


def _parse_router_intent(raw_text: str) -> str:
    """從模型輸出中寬鬆萃取意圖，不要求完美格式（HF 模型不保證吐出乾淨字串）"""
    text = (raw_text or "").strip().upper()
    if "DESIGN_DOC" in text:
        return "DESIGN_DOC"
    if "GENERAL" in text:
        return "GENERAL"
    raise RouterParseError(f"無法從輸出解析意圖: {raw_text!r}")


class PipelineMultiAgentSystem:

    def __init__(self, mcp_tools=None):
        # 1. 按流水線階段劃分工具
        # 階段二：設計與結構驗證
        self.designer_tools = [
            validate_design_json,
            search_official_knowledge_base,
            generate_design_doc,
        ]
        # 階段三：測試與輔助功能
        self.tester_tools = [
            get_weather,
        ] + (mcp_tools or [])

        # 2. 建立各自獨立的 ToolNode
        self.designer_tool_node = ToolNode(self.designer_tools, handle_tool_errors=True)
        self.tester_tool_node = ToolNode(self.tester_tools, handle_tool_errors=True)
        # self.tool_node = ToolNode(self.tools, handle_tool_errors=True)

        # 3. LLM 綁定各自工具
        self.designer_llm = router.bind_tools(self.designer_tools)
        self.tester_llm = router.bind_tools(self.tester_tools)
        # self.router = router.bind_tools(self.tools)

        # 專門給 router 節點用：純分類，不綁工具、不用 with_structured_output
        # （HuggingFace 推理端多半不支援 function-calling / JSON mode，
        #  改用「純文字輸出 + 手動寬鬆解析 + 一次重試 + 保底 fallback」）
        self.router_llm = router

        self.langfuse = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST", "http://langfuse-server:3000"),
        )

        self.graph = self._build_graph()  # 光速建立一個最簡單的圖：START -> llm -> END

        self.compiler = DynamicGraphCompiler(state_schema=State)

    # ---- Agent Nodes ----
    def _router_node(self):
        def call(state: State, config: RunnableConfig):
            last_user_msg = state["messages"][-1]
            content = last_user_msg.content if hasattr(last_user_msg, "content") else str(last_user_msg)

            # 規則優先：偵測到原始碼檔案路徑，直接判定，不問 LLM
            if FILE_PATH_PATTERN.search(content):
                return {"messages": [], "intent": "DESIGN_DOC"}

            # 規則沒命中，才交給 LLM 做分類
            classification_prompt = """判斷使用者意圖，只回答以下其中一個詞，不要有其他任何文字或標點：
DESIGN_DOC
GENERAL

DESIGN_DOC：要求根據原始碼/檔案生成設計書、式樣書、Excel
GENERAL：天氣查詢、官方知識庫問答、閒聊、其他"""
            messages = [("system", classification_prompt)] + state["messages"]

            response = self.router_llm.invoke(messages, config=config)
            raw_text = response.content if isinstance(response.content, str) else str(response.content)

            try:
                intent = _parse_router_intent(raw_text)
            except RouterParseError:
                # 第一次解析失敗，重試一次，加強約束
                retry_messages = messages + [
                    ("user", "你剛才的回答格式不對，請重新只回答 DESIGN_DOC 或 GENERAL 這兩個詞其中一個，不要有任何其他文字。")
                ]
                response = self.router_llm.invoke(retry_messages, config=config)
                raw_text = response.content if isinstance(response.content, str) else str(response.content)
                try:
                    intent = _parse_router_intent(raw_text)
                except RouterParseError:
                    # 兩次都失敗，安全 fallback：不卡住流程，走保守路徑
                    intent = "GENERAL"

            return {"messages": [], "intent": intent}
        return call

    def _designer_node(self):
        def call(state: State, config: RunnableConfig):
            messages = [("system", DESIGNER_SYSTEM_PROMPT)] + state["messages"]
            response = self.designer_llm.invoke(messages, config=config)
            return {"messages": [response]}
        return call

    def _tester_node(self):
        def call(state: State, config: RunnableConfig):
            messages = [("system", TESTER_SYSTEM_PROMPT)] + state["messages"]
            response = self.tester_llm.invoke(messages, config=config)
            return {"messages": [response]}
        return call

    def _build_graph(self):
        graph = StateGraph(State)

        # 1. 註冊所有 Agent 與 Tools 節點
        graph.add_node("router", self._router_node())
        graph.add_node("designer", self._designer_node())
        graph.add_node("designer_tools", self.designer_tool_node)

        graph.add_node("tester", self._tester_node())
        graph.add_node("tester_tools", self.tester_tool_node)

        # 2. 起點 -> 路由
        graph.add_edge(START, "router")

        def router_condition(state: State):
            return "designer" if state.get("intent") == "DESIGN_DOC" else "tester"

        graph.add_conditional_edges("router", router_condition, {"designer": "designer", "tester": "tester"})

        # 階段二條件控制 (Designer -> Tools 或 下一階段 tester)
        def designer_condition(state: State):
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                return "designer_tools"
            return "tester"

        graph.add_conditional_edges("designer", designer_condition, {"designer_tools": "designer_tools", "tester": "tester"})
        graph.add_edge("designer_tools", "designer")

        # 階段三條件控制 (Tester -> Tools 或 結束 END)
        def tester_condition(state: State):
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                return "tester_tools"
            return END

        graph.add_conditional_edges(
            "tester",
            tester_condition,
            {"tester_tools": "tester_tools", END: END},
        )
        graph.add_edge("tester_tools", "tester")

        return graph.compile(checkpointer=MemorySaver())

    def deploy_or_update_flow(self, ui_graph_json, tools_list, model):
        print("收到 UI 新的畫布結構，開始重新編譯...")
        self.graph = self.compiler.compile_from_json(
            ui_graph_json, tools_list=tools_list, model=model
        )

    async def ainvoke(self, inputs, config: dict):
        if not self.graph:
            raise ValueError("請先從 UI 畫布編譯並部署工作流！")
        try:
            # 4. 正常執行 LangGraph
            return await self.graph.ainvoke(inputs, config)
        finally:
            # 💡 5. 關鍵：無論成功或失敗，在非同步程式結束前，強迫將緩衝區的數據推送到 Langfuse Dashboard
            print("⏳ 正在將 LangGraph 執行軌跡同步至 Langfuse...")
            try:
                # 🌟 v4 SDK 提供的异步/同步兼容的强刷机制（内部会处理 OTel 的 flush）
                self.langfuse.flush()
            except (ImportError, Exception) as e:
                print(f"⚠️ Langfuse 同步失敗: {e}")

    async def astream(self, inputs, config: dict, stream_mode: str = "updates"):
        if not self.graph:
            raise ValueError("請先從 UI 畫布編譯並部署工作流！")

        try:
            # 💡 4. 使用 async for 代理底層 app.astream 的每一次產出（yield）
            async for chunk in self.graph.astream(
                inputs, config=config, stream_mode=stream_mode
            ):
                yield chunk  # 將每一個 chunk 實時吐給前端
        finally:
            # 💡 5. 關鍵：當流式輸出結束、或被用戶中斷（如斷開連線）時，強迫推送追蹤數據
            print("⏳ [Stream] 正在將 LangGraph 流式軌跡同步至 Langfuse...")
            try:
                # 🌟 流式结束或客户端主动断开（GeneratorExit）都会触发这里
                self.langfuse.flush()
            except (ImportError, Exception) as e:
                print(f"⚠️ Langfuse [Stream] 同步失敗: {e}")