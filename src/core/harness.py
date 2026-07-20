# core/harness.py
import os
import asyncio
import threading
import traceback
import queue
from typing import List

# FastMCP 3.4.2+ 高階客戶端
from fastmcp import Client
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools

from langfuse.langchain import CallbackHandler

from src.core.agent import Agent
from unittest.mock import MagicMock
import logging

logger = logging.getLogger("API_SERVICE1")


class AgentHarness:
    """
    Agent Harness (駕馭層 / 運行殼)
    使用 FastMCP 簡化遠端 MCP 服務的連接與工具鏈整合
    """

    def __init__(self, mcp_server_url: str = None):
        # 優先使用傳入的參數，其次讀取環境變數，最後使用默認值
        self.mcp_server_url = os.getenv(
            "MCP_SERVER_URL1", "http://127.0.0.1:8001/mcp"
        )
        print(f"🚀 [Harness] 預備連接至 MCP 伺服器: {self.mcp_server_url}")

        self.loop = asyncio.new_event_loop()
        self.agent_core = None  # 存放核心大腦
        self._thread = None
        self.client = None

        # Initialize Langfuse CallbackHandler for Langchain (tracing)
        self.langfuse_handler = CallbackHandler()


        print(os.getenv("LANGFUSE_HOST"))
        print(os.getenv("LANGFUSE_PUBLIC_KEY"))
        print(os.getenv("LANGFUSE_SECRET_KEY"))

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _async_init(self):
        """在背景 Loop 中打通網路管道，自動轉換並裝載內核工具"""
        lc_tools: List[BaseTool] = []
        try:
            print(f"🔄 [Harness] 正在建立 FastMCP 連接: {self.mcp_server_url}")

            # 1. 初始化 FastMCP Client (支援 http/https/ws/wss 或 local command)
            self.client = Client(self.mcp_server_url)

            # 2. 透過 __aenter__ 或 context 管理建立連線
            await self.client.__aenter__()
            print("✨ [Harness] MCP 網路管道打通成功！")

            # 3. 🌟 真正修正：利用 langchain-mcp-adapters 转换工具
            # fastmcp 的 client.session 才是底层的 MCP Session 对象
            if self.client.session:
                lc_tools = await load_mcp_tools(self.client.session)
            else:
                raise RuntimeError("FastMCP Session 未成功建立")

            print("转换后的实际类型:", [type(t) for t in lc_tools])
            print(
                f"✅ [Harness] 成功自動轉換並裝載 {len(lc_tools)} 個 LangChain 生態工具"
            )

        except Exception as e:
            print(f"🛑 [Harness Warning] MCP 管道建立失敗，降級為純本地運行。原因: {e}")
            traceback.print_exc()

        # 4. 傳入轉換完成的工具給 Agent
        self.agent_core = Agent(mcp_tools=lc_tools)

    def bootstrap(self):
        """啟動 Harness 背景殼環境"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(self._async_init(), self.loop)
        return future.result(timeout=60)

    def interact(self, user_message: str, thread_id: str) -> str:
        """多端複用的標準同步交互接口（門面模式）"""
        if not self.agent_core:
            raise RuntimeError("Harness 運行殼尚未就緒！")

        inputs = {"messages": [("user", user_message)]}
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [self.langfuse_handler],
        }

        # future = asyncio.run_coroutine_threadsafe(
        #     self.agent_core.app.ainvoke(inputs, config), self.loop
        # )
        # 舊寫法： 提前把舊圖的 ainvoke 抓出來當成參數打包，導致重新構建後，被打包的舊圖在 Thread 裡「與世隔絕」地執行。

        # 新寫法： 把 self.agent_core 這個大容器傳進去，讓它在事件循環的 Thread 裡「要執行的那一瞬間」才去 self.agent_core.app 拔取最新的圖。
        async def call_wrapper():
            return await self.agent_core.ainvoke(inputs, config)

        future = asyncio.run_coroutine_threadsafe(call_wrapper(), self.loop)
        result = future.result()
        return result["messages"][-1].content

    async def interact_stream(self, user_message: str, thread_id: str):
        """專供 FastAPI 呼叫的真·異步流式接口（終極穩定版：改用 updates 模式精準分離狀態與對話）"""
        if not self.agent_core:
            raise RuntimeError("Harness 運行殼尚未就緒！")

        inputs = {"messages": [("user", user_message)]}
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [self.langfuse_handler],
        }

        async_q = asyncio.Queue()

        async def producer():
            try:
                # 🚀 關鍵改動：改用 stream_mode="updates"，按節點（Node）產出結果
                async for chunk in self.agent_core.astream(
                    inputs, config, stream_mode="updates"
                ):
                    logger.debug(f"[interact_stream] 收到原始 chunk: {chunk}")   # ← 加这一行
                    # 1. 🔍 偵測到進入了工具執行節點 (通常叫 tools 或 call_mcp_tool)
                    if "tools" in chunk:
                        tool_messages = chunk["tools"].get("messages", [])
                        for msg in tool_messages:
                            # 這是 MCP 真正回傳結果的時候，我們在這裡發送漂亮的進度條，並封鎖背後的原始 JSON 文字
                            tool_name = getattr(msg, "name", "")
                            status_mapping = {
                                "find_user_by_username": "\n\n🤖 **Kiapi Assistant** 正在確認會員資訊... ✓\n",
                                "find_product_by_name": "🔍 正在確認商品庫存與價格... ✓\n",
                                "create_agent_order": "📦 正在為您建立系統訂單... ✓\n",
                            }
                            if tool_name in status_mapping:
                                await async_q.put(status_mapping[tool_name])
                        continue  # 🛑 絕對不讓 tools 的原始 JSON 內容漏到前端

                    # 2.  偵測到進入了大腦思考節點 (通常叫 agent)
                    if "agent" in chunk:
                        agent_messages = chunk["agent"].get("messages", [])
                        if agent_messages:
                            last_msg = agent_messages[-1]

                            # 如果這個 AIMessage 帶有 tool_calls，代表大模型正要「準備」去點擊工具
                            # 為了確保流程不中斷，我們不能在這裡阻斷它，讓它在背景靜默流轉即可
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                continue

                            # 只有當大模型「真正要對人類說話（最後的結論）」時，才把 content 放行
                            if hasattr(last_msg, "content") and last_msg.content:
                                content = last_msg.content
                                if isinstance(content, str):
                                    await async_q.put(content)
                                elif isinstance(content, list):
                                    for item in content:
                                        if (
                                            isinstance(item, dict)
                                            and item.get("type") == "text"
                                        ):
                                            await async_q.put(item.get("text", ""))
                                        elif hasattr(item, "text"):
                                            await async_q.put(item.text)

            except Exception as e:
                await async_q.put(e)
            finally:
                await async_q.put(None)  # 結束標記

        # 投遞到後台 loop 異步執行
        logger.info(f"[interact_stream] self.loop 狀態檢查: is_running={self.loop.is_running()}, is_closed={self.loop.is_closed()}")

        future = asyncio.run_coroutine_threadsafe(producer(), self.loop)

        # 關鍵：加一個回調，一旦 producer() 內部有任何調度層面的失敗，立刻打印出來
        def _on_producer_done(fut):
            try:
                fut.result()  # 如果 producer() 執行過程中有異常，這裡會重新拋出
            except Exception:
                logger.error(f"[interact_stream] producer 協程執行失敗:\n{traceback.format_exc()}")

        future.add_done_callback(_on_producer_done)

        # 在當前異步上下文中消費這個隊列
        while True:
            item = await async_q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def interact_stream_sync(self, user_message: str, thread_id: str):
        """專門餵給 Streamlit 用的同步流式接口（跨執行緒橋接）"""
        if not self.agent_core:
            raise RuntimeError("Harness 運行殼尚未就緒！")

        # 建立一個執行緒安全的同步隊列
        sync_q = queue.Queue()

        async def _async_producer():
            try:
                # 呼叫上面的異步生成器並轉存到同步隊列
                async for token in self.interact_stream(user_message, thread_id):
                    sync_q.put(token)
            except Exception as e:
                sync_q.put(e)
            finally:
                sync_q.put(None)

        # 投遞到後台線程去執行
        asyncio.run_coroutine_threadsafe(_async_producer(), self.loop)

        # 在 Streamlit 的主執行緒（同步環境）中消費這個隊列
        while True:
            item = sync_q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    async def close(self):
        """釋放 FastMCP 客戶端資源"""
        if self.client:
            await self.client.__aexit__(None, None, None)
