import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from src.core.tools.tools import (
    get_weather,
    search_official_knowledge_base,
    validate_design_json,
    generate_excel,
)
from src.core.tools.generate_design_doc import (
    generate_design_doc,
)
from src.core.workflow import DynamicGraphCompiler
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from src.core.llm_router import router
from src.core.prompts import AGENT_SYSTEM_PROMPT

# import atexit
# atexit.register(self.langfuse.flush)


class State(TypedDict):
    messages: Annotated[list, add_messages]


class Agent:
    def __init__(self, mcp_tools=None):
        self.tools = [
            get_weather,
            search_official_knowledge_base,
            validate_design_json,
            generate_excel,
            generate_design_doc,
        ] + (mcp_tools or [])
        self.tool_node = ToolNode(self.tools)

        self.graph = self._build_graph()  # 光速建立一個最簡單的圖：START -> llm -> END
        self.compiler = DynamicGraphCompiler(state_schema=State)
        self.langfuse = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST", "http://langfuse-server:3000"),
        )
        self.router = router.bind_tools(self.tools)


    def _model(self):


        def call(state: State, config: RunnableConfig):

            current_messages = state["messages"]

            messages_with_sys = [
                ("system", AGENT_SYSTEM_PROMPT)
            ] + current_messages

            response = self.router.invoke(
                messages_with_sys,
                config=config,
            )

            return {
                "messages": [response]
            }

        return call


    def _build_graph(self):
        graph = StateGraph(State)
        graph.add_node("agent", self._model())
        graph.add_node(
            "tools", self.tool_node, retry={"max_attempts": 1, "retry_on": Exception}
        )
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", tools_condition)
        graph.add_edge("tools", "agent")
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
            except Exception as e:
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
            except Exception as e:
                print(f"⚠️ Langfuse [Stream] 同步失敗: {e}")
