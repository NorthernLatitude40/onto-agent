# core/agent.py
import time
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
        # 🎯 核心：這裡一定要綁定完備的 tools，LangChain 會自動幫我們把 Schema 傳給 Gemini
        gemini = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", api_key=GEMINI_API_KEY, temperature=0
        ).bind_tools(self.tools)

        openrouter = ChatOpenAI(
            model="google/gemma-4-31b-it:free",
            # model="meta-llama/llama-3-8b-instruct:free",
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0,
        ).bind_tools(self.tools)

        def call(state: State):
            current_messages = state["messages"]

            # 🛠️ 乾淨、精準的提示詞，明確告訴它你已經是圖譜分析師，且直接給答案
            sys = (
                "你現在是官方售票網站的智慧客服兼知識圖譜分析師。請嚴格遵守以下原則：\n\n"
                "【工具調用決策】\n"
                "1. 查詢用戶購買歷史/名下商品/語義推理：必須呼叫 `get_customer_products` 工具。\n"
                "   - 如果用戶提供了具體名字（如張三），傳入參數：{'name': '張三'}。\n"
                "   - 如果用戶詢問的是泛指的概念（如“哪些 Customer 買過 Product？”），這屬於知識圖譜本體推理，你必須先引導用戶提供具體的查詢對象，或者將核心概念（如 'Customer'）作為 name 參數傳入 `get_customer_products` 進行本體探針查詢。**嚴禁因無具體人名而直接調用 query_mysql！**\n"
                "2. 建立新訂單/代客下單：當用戶明確要求購票、下單時，呼叫 `create_agent_order` 工具。\n"
                "3. 複雜數據分析：當且僅當涉及財務報表、跨表聚合統計（如銷售額前三名）且上述快捷工具完全無法滿足需求時，才使用 `query_mysql`。**禁止使用 query_mysql 查詢基礎的客戶購買關係。**\n"
                "4. 退票與場館規定：優先呼叫 `search_official_knowledge_base`。\n"
                "5. 天氣查詢：呼叫 `get_weather`。\n\n"
                "【核心原則】\n"
                "1. 誠實性：工具返回的列表即為用戶購買的全部商品。請直接根據列表內容回答用戶，回答要精簡扼要，直接給出答案，禁止重複調用工具！\n"
                "2. 若工具未返回數據，請直接告知用戶無法查詢到對應記錄。"
            )

            messages_with_sys = [("system", sys)] + current_messages

            try:
                print("🔄 正在嘗試使用 [主要模型: Gemini] 處理請求...")
                response = gemini.invoke(messages_with_sys)
                print("🎉 [Gemini] 請求成功！")
            except Exception as gemini_error:
                print(f"⚠️ [Gemini] 發生異常: {gemini_error}")
                if OPENROUTER_API_KEY:
                    try:
                        print("⏳ 觸發配額限制，安全等待 1.5 秒後切換備援...")
                        time.sleep(1.5)
                        print("🚀 啟動備援機制，切換至 [備用模型: OpenRouter]...")
                        response = openrouter.invoke(messages_with_sys)
                        print("🎉 [OpenRouter] 備援成功！")
                    except Exception as router_error:
                        raise RuntimeError(f"所有模型均失效。最後錯誤: {router_error}")
                else:
                    raise gemini_error

            # 🎯 這裡只做最純粹的日誌列印，不干涉、不清洗任何參數，讓 LangChain / LangGraph 走原生校驗
            if hasattr(response, "tool_calls") and response.tool_calls:
                print("\n================ 🛠️ MCP TOOL CALL DETECTED ================")
                for tool_call in response.tool_calls:
                    print(f"📌 [工具名稱]: {tool_call.get('name')}")
                    print(f"🔑 [原始參數]: {tool_call.get('args')}")
                print("===========================================================\n")

            return {"messages": [response]}

        return call

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
