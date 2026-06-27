# # core/agent.py
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

        # 💡 將熔斷標記綁定在實例上，避免多用戶併發時互相干擾
        self.gemini_available = True

        self.app = self._build_graph()

    def _model(self):
        # 🎯 提示：如果想嘗試消除 additionalProperties 警告，可以嘗試 strict=False（取決於 langchain 版本）
        gemini = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", api_key=GEMINI_API_KEY, temperature=0
        ).bind_tools(self.tools, strict=False)

        openrouter = ChatOpenAI(
            model="google/gemma-4-31b-it:free",
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0,
        ).bind_tools(self.tools)

        def call(state: State):
            # 💡 透過閉包直接讀寫實例屬性，不再需要 global
            current_messages = state["messages"]

            sys = (
                "你現在是紐西蘭巴士旅遊（Kiwi Experience）官方售票網站的「智慧客服兼知識圖譜分析師」。你具備調用多個後端工具的能力，必須根據用戶的自然語言意圖，做出最正確的工具調用決策。\n\n"
                "【資料庫圖結構知識 (Schema & Context)】\n"
                "當前圖資料庫使用了 RDF/OWL 本體架構導入（n10s 插件），所有自定義的類別和屬性都帶有 `ns0__` 前綴：\n"
                "1. 節點標籤 (Labels)：\n"
                "   - `ns0__HopOnHopOffDeal`: 隨上隨下巴士旅遊特惠行程節點（為 TourDeal 的子類）\n"
                "   - `ns0__City`: 城市節點\n"
                "   - `Resource`: 所有 RDF 實體節點的通用標籤\n"
                "2. 節點內部屬性 (Properties)：\n"
                '   - `rdfs__label`: 人類可讀的名稱（如行程名稱 "Buzzy Bee"、城市名 "Auckland"）\n'
                "   - `ns0__priceNZD`: 行程價格（數值型態，Float）\n"
                "   - `ns0__durationDays`: 行程天數（整數，Integer）\n"
                "   - `ns0__discountPercent`: 折扣百分比（整數，Integer）\n"
                "3. 關係類型 (Relationships)：\n"
                "   - `[:ns0__startsFrom]`: 從某城市出發 (Deal -> City)\n"
                "   - `[:ns0__endsAt]`: 抵達某城市 (Deal -> City)\n\n"
                "【工具調用決策】\n"
                "1. 查詢旅遊特惠行程 / 城市出發關聯 / 語義推理：必須呼叫 `get_tour_deals_by_city` 工具。\n"
                "   - 如果用戶提供了具體城市（如奧克蘭），傳入參數：{'city_name': 'Auckland'}。\n"
                "   - 如果用戶詢問的是泛指的概念（如“有哪些 TourDeal？”、“進行語義推理查詢”），這屬於知識圖谱本體推理，你必須將核心概念（如 'TourDeal' 或 'City'）作為 city_name 參數傳入工具進行本體探針查詢。**嚴禁因無具體城市名而直接調用 query_mysql！**\n"
                "2. 建立新訂單 / 代客下單：當用戶明確要求預訂行程、購票、下單時，呼叫 `create_agent_order` 工具。\n"
                "3. 複雜財務數據分析：當且僅當涉及公司財務報表、跨表營收聚合統計（如月度銷售額前三名）且上述圖譜工具完全無法滿足需求時，才使用 `query_mysql`。**禁止使用 query_mysql 查詢基礎的行程、城市、出發地等關係。**\n"
                "4. 退改簽與乘車/場館規定：優先呼叫 `search_official_knowledge_base`（官方知識庫）。\n"
                "5. 紐西蘭當地天氣查詢：呼叫 `get_weather`。\n\n"
                "【核心原則】\n"
                "1. 誠實性：工具返回的列表即為官方系統的真實數據。請直接根據工具回傳的富文本內容回答用戶，回答要精簡扼要，直接給出答案，禁止重複無意義地調用工具！\n"
                "2. 若工具未返回任何數據，請直接禮貌地告知用戶無法查詢到對應的行程或記錄。"
            )

            messages_with_sys = [("system", sys)] + current_messages
            response = None

            # 🌟 根據實例的熔斷標記動態選擇
            if self.gemini_available:
                try:
                    print("🔄 正在嘗試使用 [主要模型: Gemini] 處理請求...")
                    response = gemini.invoke(messages_with_sys)
                    print("🎉 [Gemini] 請求成功！")
                except Exception as gemini_error:
                    print(f"⚠️ [Gemini] 發生異常: {gemini_error}")

                    # 💡 只對當前對話實例熔斷
                    self.gemini_available = False
                    print("🚨 [熔斷觸發] 當前 Agent 實例已將 Gemini 切換至備援通道。")

                    if OPENROUTER_API_KEY:
                        print("⏳ 觸發配額限制，安全等待 1.5 秒後切換備援...")
                        time.sleep(1.5)
                        print("🚀 啟動備援機制，切換至 [備用模型: OpenRouter]...")
                        try:
                            response = openrouter.invoke(messages_with_sys)
                            print("🎉 [OpenRouter] 備援成功！")
                        except Exception as router_error:
                            raise RuntimeError(
                                f"所有模型均失效。最後錯誤: {router_error}"
                            )
                    else:
                        raise gemini_error
            else:
                # 🌟 已熔斷狀態，直接走備援
                if OPENROUTER_API_KEY:
                    print(
                        "⚡ [快道運行] 偵測到 Gemini 處於熔斷狀態，直接使用 [備用模型: OpenRouter]..."
                    )
                    try:
                        response = openrouter.invoke(messages_with_sys)
                        print("🎉 [OpenRouter] 備援成功！")
                    except Exception as router_error:
                        raise RuntimeError(f"備援模型也失效。最後錯誤: {router_error}")
                else:
                    raise RuntimeError("主要模型已熔斷，且未配置備援 OpenRouter 密鑰。")

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
        graph.add_node(
            "tools", self.tool_node, retry={"max_attempts": 1, "retry_on": Exception}
        )
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", tools_condition)
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=MemorySaver())

    async def ainvoke(self, inputs, config):
        return await self.app.ainvoke(inputs, config)
