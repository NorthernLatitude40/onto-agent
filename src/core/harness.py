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

from core.agent import Agent


class AgentHarness:
    """
    Agent Harness (駕馭層 / 運行殼)
    使用 FastMCP 簡化遠端 MCP 服務的連接與工具鏈整合
    """

    def __init__(self, mcp_server_url: str = None):
        # 優先使用傳入的參數，其次讀取環境變數，最後使用默認值
        self.mcp_server_url = mcp_server_url or os.getenv(
            "MCP_SERVER_URL", "http://127.0.0.1:8001/mcp"
        )
        print(f"🚀 [Harness] 預備連接至 MCP 伺服器: {self.mcp_server_url}")

        self.loop = asyncio.new_event_loop()
        self.agent_core = None  # 存放核心大腦
        self._thread = None
        self.client = None

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
        config = {"configurable": {"thread_id": thread_id}}

        future = asyncio.run_coroutine_threadsafe(
            self.agent_core.app.ainvoke(inputs, config), self.loop
        )
        result = future.result()
        return result["messages"][-1].content

    async def interact_stream(self, user_message: str, thread_id: str):
        """專供 FastAPI 呼叫的真·異步流式接口"""
        if not self.agent_core:
            raise RuntimeError("Harness 運行殼尚未就緒！")

        inputs = {"messages": [("user", user_message)]}
        config = {"configurable": {"thread_id": thread_id}}

        # 透過一個異步隊列做跨執行緒的 Bridge 傳輸
        async_q = asyncio.Queue()

        async def producer():
            try:
                # 這裡假設 agent_core.app 是一個 LangGraph 或 LCEL RunnableSequence
                async for chunk, metadata in self.agent_core.app.astream(
                    inputs, config, stream_mode="messages"
                ):

                    if chunk and hasattr(chunk, "content"):

                        content = chunk.content

                        # 純文字
                        if isinstance(content, str):
                            await async_q.put(content)

                        # List
                        elif isinstance(content, list):

                            for item in content:

                                # OpenAI Content Block
                                if isinstance(item, dict):

                                    if item.get("extras"):
                                        continue

                                    if item.get("type") == "text":
                                        text = item.get("text")
                                        if text:
                                            await async_q.put(text)

                                # LangChain TextContent
                                elif hasattr(item, "text"):
                                    if item.text:
                                        await async_q.put(item.text)

                                # 已經是 str
                                elif isinstance(item, str):
                                    await async_q.put(item)
            except Exception as e:
                await async_q.put(e)
            finally:
                await async_q.put(None)  # 結束標記

        # 投遞到後台 loop 異步執行
        asyncio.run_coroutine_threadsafe(producer(), self.loop)

        # 在當前異步上下文（如 FastAPI 執行緒）中消費這個隊列
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
