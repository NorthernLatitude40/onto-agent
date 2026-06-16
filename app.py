import os
import asyncio
import threading
from typing import Annotated
from typing_extensions import TypedDict
import httpx
import streamlit as st
import sys
import traceback

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

# 引入新版通訊模組
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from contextlib import AsyncExitStack

# ================= 1. 初始化與環境設定 =================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

st.set_page_config(page_title="官方智慧售票 Agent (RAG+MCP版)", page_icon="🎫")
st.title("🎫 官方智慧售票 Agent")
st.caption("🚀 實戰：外掛 AnythingLLM RAG ＋ 本地 MySQL MCP ＋ 雙模型智慧切換 (執行緒安全版)")

ANYTHINGLLM_BASE_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_API_KEY = "5CWGCCF-QZMMSTT-HA2ESKA-DG24WBH"  
WORKSPACE_SLUG = "ticketrules"                  

# ================= 2. 定義 RAG 與天氣技能 =================

@tool
def search_official_knowledge_base(query: str) -> str:
    """當使用者詢問關於售票規則、退換票政策、實名制驗證、場館攜帶規定等官方政策時，呼叫此工具進行知識庫檢索。"""
    url = f"{ANYTHINGLLM_BASE_URL}/workspace/{WORKSPACE_SLUG}/chat"
    headers = {
        "Authorization": f"Bearer {ANYTHINGLLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": query,
        "mode": "query" ,
        "model": "current",     
        "temperature": 0.0    
    }
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            sources = result.get("sources", [])
            if sources:
                retrieved_texts = []
                for i, src in enumerate(sources, 1):
                    text_chunk = src.get("text", "").strip()
                    if text_chunk:
                        retrieved_texts.append(f"[文件片段 {i}] {text_chunk}")
                return "【官方知識庫檢索結果】如下：\n\n" + "\n\n".join(retrieved_texts)
            return f"【官方知識庫檢索結果】官方知識庫無關聯片段，參考回答：\n{result.get('textResponse', '')}"
        else:
            return f"知識庫連線異常，錯誤碼: {response.status_code}"
    except Exception as e:
        return f"無法讀取官方知識庫，原因: {str(e)}"

@tool
def get_weather(city: str) -> str:
    """獲取指定城市的即時天氣資訊。"""
    city_lower = city.lower()
    if "東京" in city_lower or "tokyo" in city_lower:
        return "東京目前天氣：晴朗，氣溫 18 度，非常適合看戶外演唱會。"
    elif "台北" in city_lower or "taipei" in city_lower:
        return "台北目前天氣：陰天，氣溫 22 度，體感舒適。"
    return f"暫時找不到 {city} 的天氣資訊。"


# ================= 3. 核心重構：獨立的異步 Worker 執行緒 =================

class AgentWorker:
    """
    負責在獨立執行緒中管理所有 Async 生命週期與 MCP 連線。
    對 Streamlit 暴露出純同步 (Synchronous) 的介面。
    """
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.exit_stack = AsyncExitStack()
        self.app = None
        self.thread = None

    def start_background_loop(self):
        """啟動背景 Event Loop"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start(self):
        """啟動 Worker 執行緒並初始化 Agent"""
        self.thread = threading.Thread(target=self.start_background_loop, daemon=True)
        self.thread.start()
        
        # 透過背景 loop 執行初始化
        future = asyncio.run_coroutine_threadsafe(self._async_init(), self.loop)
        return future.result() # 同步等待初始化完成

    async def _async_init(self):
        """在背景 loop 執行的非同步初始化"""
        mcp_tools = []
        try:
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["db_mcp_server.py"]
            )
            print("INITIALIZING MCP SERVER IN WORKER THREAD...")
            read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            
            await asyncio.wait_for(session.initialize(), timeout=10)
            print("STDIO OK - MCP LINK ACTIVE IN WORKER")
            
            mcp_tools = await load_mcp_tools(session)
            print(f"✅ 成功託管並載入 {len(mcp_tools)} 個 MySQL MCP 工具")
        except Exception as e:
            print(f"🛑 MCP 工具載入失敗，僅啟用本地工具。原因: {e}")
            traceback.print_exc()

        # 組裝 LangGraph
        all_tools = [get_weather, search_official_knowledge_base] + mcp_tools
        tool_node = ToolNode(all_tools)

        class State(TypedDict):
            messages: Annotated[list, add_messages]

        gemini_model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            api_key=GEMINI_API_KEY, 
            max_tokens=2048,
            temperature=0
        ).bind_tools(all_tools)
        
        openrouter_model = ChatOpenAI(
            model="google/gemma-4-31b-it:free",  
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            max_tokens=2048,
            temperature=0
        ).bind_tools(all_tools)

        def call_model(state: State):
            system_message = (
                "你現在是官方售票網站的智慧客服兼資料庫分析師。\n"
                "1. 當使用者詢問退票、場館規定時，優先呼叫 `search_official_knowledge_base`。\n"
                "2. 當使用者詢問會員消費、庫存、訂單、或要求查詢資料庫時，請使用對應的 MySQL 工具。\n"
                "請嚴格根據工具返回的內容來回答，保持誠實。回答時請精簡扼要，並直接給出答案。"
            )
            messages_with_system = [("system", system_message)] + state["messages"]
            
            try:
                print("🔄 正在嘗試使用 [主要模型: Gemini] 處理請求...")
                response = gemini_model.invoke(messages_with_system)
                print("🎉 [Gemini] 請求成功！")
                return {"messages": [response]}
            except Exception as gemini_error:
                print(f"⚠️ [Gemini] 發生異常: {gemini_error}")
                if OPENROUTER_API_KEY:
                    try:
                        print("🚀 啟動備援機制，切換至 [備用模型: OpenRouter]...")
                        response = openrouter_model.invoke(messages_with_system)
                        print("🎉 [OpenRouter] 備援成功！")
                        return {"messages": [response]}
                    except Exception as router_error:
                        raise RuntimeError(f"所有模型均失效。最後錯誤: {router_error}")
                else:
                    raise gemini_error

        workflow = StateGraph(State)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")
        
        memory = MemorySaver()
        self.app = workflow.compile(checkpointer=memory)

    def sync_invoke(self, inputs: dict, config: dict) -> dict:
        """提供給 Streamlit 呼叫的純同步介面"""
        future = asyncio.run_coroutine_threadsafe(
            self.app.ainvoke(inputs, config), 
            self.loop
        )
        return future.result() # 同步阻塞等待背景執行緒回傳結果


# 使用 Streamlit 資源快取確保 Worker 全域唯一且不重複初始化
@st.cache_resource
def get_agent_worker():
    worker = AgentWorker()
    worker.start()
    return worker

# 取得同步化的 Worker 實例
agent_worker = get_agent_worker()


# ================= 4. Streamlit 介面渲染 (純同步流程) =================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "您好！我已經成功外掛了 AnythingLLM 知識庫與本地 MySQL 資料庫。請隨時提問客服問題（如：怎麼退票？）或要求我分析資料庫數據（如：幫我查張小明買了什麼？）"}
    ]

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if user_query := st.chat_input("請輸入您的問題..."):
    with st.chat_message("user"):
        st.write(user_query)
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    
    with st.chat_message("assistant"):
        with st.spinner("Agent 決策中..."):
            config = {"configurable": {"thread_id": "ticket_agent_stream"}}
            inputs = {"messages": [("user", user_query)]}
            
            try:
                # 💡 這裡變成了純同步呼叫，完全沒有 nest_asyncio，也沒有 Async 地獄
                result = agent_worker.sync_invoke(inputs, config)
                
                final_reply = result["messages"][-1].content
                st.write(final_reply)
                st.session_state.chat_history.append({"role": "assistant", "content": final_reply})
            except Exception as final_error:
                print("❌ [Agent 執行階段崩難] 詳細錯誤軌跡如下：")
                traceback.print_exc() 
                st.error(f"🛑 系統錯誤詳細資訊：{str(final_error)}")