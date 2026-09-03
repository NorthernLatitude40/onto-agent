import asyncio
import logging
import os
import queue
import threading
import traceback
from contextlib import AsyncExitStack
from typing import AsyncGenerator, Generator, Any

from fastmcp import Client
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from langfuse.langchain import CallbackHandler

from src.core.strategies.base import BaseAgentStrategy
from src.core.strategies.factory import AgentStrategyFactory
from src.core.voyager_agent.skill_library import SkillLibrary

logger = logging.getLogger("API_SERVICE")


def _extract_stream_payload(chunk: dict) -> str | None:
    """纯函数：从 LangChain/LangGraph 的 chunk 中提取状态或文本消息"""
    # 1. 工具节点进度捕获
    tool_node_key = next((k for k in ["tools", "designer_tools", "executor_tools", "tester_tools"] if k in chunk), None)
    if tool_node_key:
        tool_messages = chunk[tool_node_key].get("messages", [])
        for msg in tool_messages:
            tool_name = getattr(msg, "name", "")
            status_text = ""
            status_mapping = {
                "validate_design_json": "📐 **[阶段一: 设计]** 正在验证 JSON 架构... ✓\n",
                "generate_excel": "📊 **[阶段二: 执行]** 正在生成 Excel 档案... ✓\n",
                "generate_design_doc": "📄 **[阶段二: 执行]** 正在产出设计文件... ✓\n",
                "get_weather": "🌤️ **[阶段三: 测试]** 正在验证... ✓\n",
            }
            if tool_name in status_mapping:
                status_text += status_mapping[tool_name]
        return status_text if status_text else None

    # 2. Agent 思考/输出节点捕获
    agent_node_key = next((k for k in ["agent", "designer", "executor", "tester"] if k in chunk), None)
    if agent_node_key:
        agent_messages = chunk[agent_node_key].get("messages", [])
        if agent_messages:
            last_msg = agent_messages[-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                return None
            if hasattr(last_msg, "content") and last_msg.content:
                content = last_msg.content
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    texts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(item.get("text", ""))
                        elif hasattr(item, "text"):
                            texts.append(item.text)
                    return "".join(texts)
    return None


class AgentHarness:
    """
    Agent Harness (驾驭层 / 运行壳)
    纯粹的基础设施壳：管理事件循环与 MCP 工具连接，支持通过策略名称动态调用不同的 Agent Graph。
    """

    def __init__(self, mcp_server_url: str | None = None):
        if mcp_server_url:
            self.mcp_server_url = mcp_server_url
        else:
            is_dev = os.getenv("ENV", "production").lower() == "development"
            default_url = "http://127.0.0.1:8001/mcp" if is_dev else "http://mcp-server:8001/mcp"
            self.mcp_server_url = os.getenv("MCP_SERVER_URL", default_url)

        logger.info(f"🚀 [Harness] 预备连接至 MCP 服务器: {self.mcp_server_url}")

        self.loop = asyncio.new_event_loop()
        self._thread: threading.Thread | None = None
        
        self._exit_stack = AsyncExitStack()
        self.client: Client | None = None
        self.mcp_tools: list[BaseTool] = []

        # 👈 2. 初始化並持有 SkillLibrary 實例
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        gemini_api_key = os.getenv("GEMINI_API_KEY")

        if supabase_url and supabase_key and gemini_api_key:
            self.skill_library = SkillLibrary(
                supabase_url=supabase_url,
                supabase_key=supabase_key,
                gemini_api_key=gemini_api_key,
            )
            logger.info("✅ [Harness] Voyager SkillLibrary 初始化成功！")
        else:
            self.skill_library = None
            logger.warning("⚠️ [Harness] 缺少 Supabase 或 Gemini 金鑰，SkillLibrary 未初始化。")
        
        # 内部缓存已构建的策略对象，避免重复 Build
        self._strategies: dict[str, BaseAgentStrategy] = {}

        self.langfuse_handler = CallbackHandler()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()

    async def _async_init(self) -> None:
        """在背景 Loop 中打通网络管道，加载基础 MCP 工具"""
        try:
            logger.info(f"🔄 [Harness] 正在建立 FastMCP 连接: {self.mcp_server_url}")

            self.client = Client(self.mcp_server_url)
            async with asyncio.timeout(3.0):
                await self._exit_stack.enter_async_context(self.client)
            logger.info("✨ [Harness] MCP 网络管道打通成功！")

            if self.client.session:
                self.mcp_tools = await load_mcp_tools(self.client.session)
            else:
                raise RuntimeError("FastMCP Session 未成功建立，无法加载工具")

            logger.info(f"✅ [Harness] 成功自动转换并装载 {len(self.mcp_tools)} 个 LangChain 工具")

        except (Exception, asyncio.TimeoutError) as e:
                # 連接失敗或逾時不拋出異常，僅記錄 Warning 並掠過
                logger.warning(
                    f"⚠️ MCP 服務器不可用或連接失敗 ({e})，自動跳過 MCP 工具，繼續啟動系統..."
                )
                self.client = None  # 將 client 標記為 None，避免後續誤用

    def bootstrap(self, timeout: float = 60.0) -> "AgentHarness":
        """启动 Harness 背景线程并同步等待初始化完成"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="HarnessLoopThread")
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(self._async_init(), self.loop)
        
        try:
            future.result(timeout=timeout)
            return self
        except Exception as e:
            logger.critical(f"💥 [Harness] Bootstrap 初始化超时或失败: {e}")
            self.shutdown()
            raise e

    def _get_or_build_strategy(self, strategy_or_name: BaseAgentStrategy | str) -> BaseAgentStrategy:
        """从缓存获取或初始化并构建指定策略"""
        if isinstance(strategy_or_name, BaseAgentStrategy):
            if not strategy_or_name.graph:
                strategy_or_name.build(mcp_tools=self.mcp_tools)
            return strategy_or_name

        strategy_name = strategy_or_name
        if strategy_name not in self._strategies:
            logger.info(f"🛠️ [Harness] 正在首次加载并构建 Agent 策略: [{strategy_name}]")
            strategy_obj = AgentStrategyFactory.create(strategy_name)
            strategy_obj.build(mcp_tools=self.mcp_tools, skill_library=self.skill_library)
            self._strategies[strategy_name] = strategy_obj

        return self._strategies[strategy_name]

    def interact(
        self, 
        user_message: str, 
        thread_id: str, 
        strategy: BaseAgentStrategy | str = "shop",
        extra_config: dict[str, Any] | None = None,
        timeout: float = 180.0
    ) -> str:
        """同步阻塞交互接口（Facade 模式）"""
        target_strategy = self._get_or_build_strategy(strategy)

        try:
            current_loop = asyncio.get_running_loop()
            if current_loop is self.loop:
                raise RuntimeError("❌ 严禁在 Harness 事件循环线程内部调用同步 interact()！")
        except RuntimeError:
            pass

        inputs = {"messages": [("user", user_message)]}

        configurable = {"thread_id": thread_id}
        if extra_config:
            configurable.update(extra_config)
        
        config = {
            "configurable": configurable,
            "callbacks": [self.langfuse_handler],
        }

        async def _call_wrapper():
            return await target_strategy.ainvoke(inputs, config)

        future = asyncio.run_coroutine_threadsafe(_call_wrapper(), self.loop)
        
        try:
            result = future.result(timeout=timeout)
            return result
        except (TimeoutError, asyncio.TimeoutError):
            logger.error(f"⏱️ [interact] 执行超时 ({timeout}s)")
            raise TimeoutError("Agent 响应超时，请稍后重试。")

    async def interact_stream(
        self, 
        user_message: str, 
        thread_id: str,
        strategy: BaseAgentStrategy | str = "shop",
        extra_config: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """专供 FastAPI 调用的异步流式接口"""
        target_strategy = self._get_or_build_strategy(strategy)

        inputs = {"messages": [("user", user_message)]}
        configurable = {"thread_id": thread_id}
        if extra_config:
            configurable.update(extra_config)

        config = {
            "configurable": configurable,
            "callbacks": [self.langfuse_handler],
        }

        main_loop = asyncio.get_running_loop()
        main_q: asyncio.Queue = asyncio.Queue()

        def _safe_put(item: Any):
            main_loop.call_soon_threadsafe(main_q.put_nowait, item)

        async def producer():
            try:
                async for chunk in target_strategy.astream(inputs, config, stream_mode="updates"):
                    payload = _extract_stream_payload(chunk)
                    if payload:
                        _safe_put(payload)
            except BaseException as e:
                logger.error(f"❌ [Producer] 节点执行异常: {e}", exc_info=True)
                _safe_put(e)
            finally:
                _safe_put(None)

        asyncio.run_coroutine_threadsafe(producer(), self.loop)

        while True:
            item = await main_q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def interact_stream_sync(
        self, 
        user_message: str, 
        thread_id: str,
        strategy: BaseAgentStrategy | str = "shop",
        extra_config: dict[str, Any] | None = None
    ) -> Generator[str, None, None]:
        """专供 Streamlit / CLI 调用的同步流式接口"""
        target_strategy = self._get_or_build_strategy(strategy)

        sync_q: queue.Queue = queue.Queue()
        inputs = {"messages": [("user", user_message)]}
        configurable = {"thread_id": thread_id}
        if extra_config:
            configurable.update(extra_config)

        config = {
            "configurable": configurable,
            "callbacks": [self.langfuse_handler],
        }

        async def _async_producer():
            try:
                async for chunk in target_strategy.astream(inputs, config, stream_mode="updates"):
                    payload = _extract_stream_payload(chunk)
                    if payload:
                        sync_q.put(payload)
            except Exception as e:
                logger.error(f"❌ [Sync Producer] 执行异常: {e}", exc_info=True)
                sync_q.put(e)
            finally:
                sync_q.put(None)

        asyncio.run_coroutine_threadsafe(_async_producer(), self.loop)

        while True:
            item = sync_q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def shutdown(self) -> None:
        """优雅停机"""
        logger.info("🛑 [Harness] 正在优雅关闭 Harness 资源...")

        if self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._exit_stack.aclose(), self.loop)
            try:
                future.result(timeout=10)
            except Exception as e:
                logger.error(f"⚠️ [Harness] 关闭 AsyncExitStack 异常: {e}")

            self.loop.call_soon_threadsafe(self.loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        logger.info("👋 [Harness] 资源已完全释放。")

_harness_instance: AgentHarness | None = None

def get_harness() -> AgentHarness:
    """获取/懒加载 Harness 单例"""
    global _harness_instance
    if _harness_instance is None:
        _harness_instance = AgentHarness()
        _harness_instance.bootstrap()
    return _harness_instance

# =====================================================================
# 全局唯一 Harness 单例导出与自动启动
# =====================================================================
harness = get_harness()