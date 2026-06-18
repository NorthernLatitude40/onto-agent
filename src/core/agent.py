from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.config.config import GEMINI_API_KEY, OPENROUTER_API_KEY
from core.tools import get_weather, search_official_knowledge_base


class State(TypedDict):
    messages: Annotated[list, add_messages]


class Agent:
    def __init__(self, mcp_tools=None):
        self.tools = [get_weather, search_official_knowledge_base] + (mcp_tools or [])
        self.tool_node = ToolNode(self.tools)
        self.app = self._build_graph()

    def _model(self):
        gemini = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=GEMINI_API_KEY,
            temperature=0
        ).bind_tools(self.tools)

        openrouter = ChatOpenAI(
            model="google/gemma-4-31b-it:free",
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
        ).bind_tools(self.tools)

        def call(state: State):
            msgs = state["messages"]

            sys = ("你是售票客服，必须优先使用工具。")
            messages = [("system", sys)] + msgs

            try:
                return {"messages": [gemini.invoke(messages)]}
            except:
                return {"messages": [openrouter.invoke(messages)]}

        return call

    def _call_model(self, state: State):
        system_message = (
            "你現在是官方售票網站的智慧客服兼資料庫分析師。\n"
            "1. 當使用者詢問退票、場館規定時，優先呼叫 `search_official_knowledge_base`。\n"
            "2. 當使用者詢問會員消費、庫存、訂單、或要求查詢資料庫時，請使用對應的 MySQL 工具。\n"
            "3. 當使用者要求執行測試或評估時，請呼叫 `run_agent_evaluation` 工具。\n"
            "請嚴格根據工具返回的內容來回答，保持誠實。回答時請精簡扼要，並直接給出答案。"
        )
        messages_with_system = [("system", system_message)] + state["messages"]
        
        try:
            print("🔄 正在嘗試使用 [主要模型: Gemini] 處理請求...")
            response = self.gemini_model.invoke(messages_with_system)
            print("🎉 [Gemini] 請求成功！")
            return {"messages": [response]}
        except Exception as gemini_error:
            print(f"⚠️ [Gemini] 發生異常: {gemini_error}")
            if OPENROUTER_API_KEY:
                try:
                    print("🚀 啟動備援機制，切換至 [備用模型: OpenRouter]...")
                    response = self.openrouter_model.invoke(messages_with_system)
                    print("🎉 [OpenRouter] 備援成功！")
                    return {"messages": [response]}
                except Exception as router_error:
                    raise RuntimeError(f"所有模型均失效。最後錯誤: {router_error}")
            else:
                raise gemini_error

    def _build_graph(self):
        graph = StateGraph(State)

        graph.add_node("agent", self._model())
        graph.add_node("tools", self.tool_node)

        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", tools_condition)
        graph.add_edge("tools", "agent")

        return graph.compile(checkpointer=MemorySaver())

    async def ainvoke(self, inputs, config):
        return await self.app.ainvoke(inputs, config)