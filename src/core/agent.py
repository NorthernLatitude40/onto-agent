import time
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

from src.config.config import GEMINI_API_KEY, OPENROUTER_API_KEY

# 🎯 提示：請在 config 檔案中配置 HUGGINGFACEHUB_API_TOKEN
from src.config.config import HUGGINGFACEHUB_API_TOKEN

from src.core.tools import (
    get_weather,
    search_official_knowledge_base,
    validate_design_json,
    generate_excel,
)
from src.core.workflow import DynamicGraphCompiler
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse

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
        ] + (mcp_tools or [])
        self.tool_node = ToolNode(self.tools)

        # 💡 將熔斷標記綁定在實例上，避免多用戶併發時互相干擾
        self.gemini_available = True
        self.openrouter_available = (
            True  # 🚀 新增 OpenRouter 狀態追蹤，用以決定是否降級至 HF
        )

        self.app = self._build_graph()  # 光速建立一個最簡單的圖：START -> llm -> END
        self.compiler = DynamicGraphCompiler(state_schema=State)
        self.langfuse = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST", "http://langfuse-server:3000"),
        )

    def _model(self):
        # 1️⃣ 主要模型：Gemini
        gemini = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", api_key=GEMINI_API_KEY, temperature=0
        ).bind_tools(self.tools, strict=False)

        # 2️⃣ 第一備援：OpenRouter (Gemma)
        openrouter = ChatOpenAI(
            model="google/gemma-4-31b-it:free",
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0,
        ).bind_tools(self.tools)

        # 3️⃣ 第二備援：Hugging Face (以 Qwen2.5-7B-Instruct 為例)
        # 注意：使用工具綁定（Tool Calling）需要 HF 模型本身有支援（如 Qwen, Llama3）
        llm_hf = HuggingFaceEndpoint(
            repo_id="Qwen/Qwen2.5-7B-Instruct",
            huggingfacehub_api_token=HUGGINGFACEHUB_API_TOKEN,
            temperature=0.1,
            task="text-generation",
        )
        huggingface = ChatHuggingFace(llm=llm_hf).bind_tools(self.tools)

        def call(state: State, config: RunnableConfig):
            current_messages = state["messages"]

            sys = (
                "你現在是跟我走官方售票網站的「智慧客服兼知識圖譜分析師」。你具備調用多個後端工具的能力，必須根據用戶的自然語言意圖，做出最正確的工具調用決策。\n\n"
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

            # --- 🤖 階層式模型路由與熔斷狀態機 ---

            # 第一階段：嘗試主要模型 (Gemini)
            if self.gemini_available:
                try:
                    print("🔄 [Level 1] 正在嘗試使用 [主要模型: Gemini] 處理請求...")
                    response = gemini.invoke(messages_with_sys, config=config)
                    print("🎉 [Gemini] 請求成功！")
                    return {"messages": [response]}
                except Exception as gemini_error:
                    print(f"⚠️ [Gemini] 發生異常: {gemini_error}")
                    self.gemini_available = False
                    print("🚨 [熔斷觸發] 當前 Agent 實例已將 Gemini 切換至備援通道。")
                    time.sleep(1.5)  # 配額緩衝

            # 第二階段：嘗試第一備援 (OpenRouter)
            if self.openrouter_available and OPENROUTER_API_KEY:
                try:
                    print("🚀 [Level 2] 正在嘗試使用 [備用模型 1: OpenRouter]...")
                    response = openrouter.invoke(messages_with_sys, config=config)
                    print("🎉 [OpenRouter] 備援成功！")
                    return {"messages": [response]}
                except Exception as router_error:
                    print(f"⚠️ [OpenRouter] 發生異常: {router_error}")
                    self.openrouter_available = False
                    print("🚨 [二次熔斷] OpenRouter 失效，準備調度終極備援。")
                    time.sleep(1.0)

            # 第三階段：嘗試第二備援 (Hugging Face)
            if HUGGINGFACEHUB_API_TOKEN:
                try:
                    print(
                        "⚡ [Level 3] 進入終極備援，正在嘗試使用 [備用模型 2: Hugging Face]..."
                    )
                    response = huggingface.invoke(messages_with_sys, config=config)
                    print("🎉 [Hugging Face] 終極備援成功！")

                    # 印出 MCP 軌跡調試資訊
                    if hasattr(response, "tool_calls") and response.tool_calls:
                        print(
                            "\n================ 🛠️ MCP TOOL CALL DETECTED ================"
                        )
                        for tool_call in response.tool_calls:
                            print(f"📌 [工具名稱]: {tool_call.get('name')}")
                            print(f"🔑 [原始參數]: {tool_call.get('args')}")
                        print(
                            "===========================================================\n"
                        )

                    return {"messages": [response]}
                except Exception as hf_error:
                    raise RuntimeError(
                        f"💥 核心崩潰：所有 LLM 模型層級均已失效。最後錯誤: {hf_error}"
                    )
            else:
                raise RuntimeError(
                    "主要與次要模型均失效，且未配置 HUGGINGFACEHUB_API_TOKEN 終極備援。"
                )

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
        self.app = self.compiler.compile_from_json(
            ui_graph_json, tools_list=tools_list, model=model
        )

    async def ainvoke(self, inputs, config: dict):
        if not self.app:
            raise ValueError("請先從 UI 畫布編譯並部署工作流！")
        try:
            # 4. 正常執行 LangGraph
            return await self.app.ainvoke(inputs, config)
        finally:
            # 💡 5. 關鍵：無論成功或失敗，在非同步程式結束前，強迫將緩衝區的數據推送到 Langfuse Dashboard
            print("⏳ 正在將 LangGraph 執行軌跡同步至 Langfuse...")
            try:
                # 🌟 v4 SDK 提供的异步/同步兼容的强刷机制（内部会处理 OTel 的 flush）
                self.langfuse.flush()
            except Exception as e:
                print(f"⚠️ Langfuse 同步失敗: {e}")

    async def astream(self, inputs, config: dict, stream_mode: str = "updates"):
        if not self.app:
            raise ValueError("請先從 UI 畫布編譯並部署工作流！")

        try:
            # 💡 4. 使用 async for 代理底層 app.astream 的每一次產出（yield）
            async for chunk in self.app.astream(
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
