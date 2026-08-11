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

from src.core.agent import PipelineMultiAgentSystem

# 使用统一定义的 Logger
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
    封装事件循环与 FastMCP 工具载入，提供跨同步/异步环境的统一 Agent 调用接口。
    """

    def __init__(self, mcp_server_url: str | None = None):
        # 1. 动态确定 MCP 服务地址：优先参数 -> 环境变量 -> 视 ENV 自动回退
        if mcp_server_url:
            self.mcp_server_url = mcp_server_url
        else:
            is_dev = os.getenv("ENV", "production").lower() == "development"
            default_url = "http://127.0.0.1:8001/mcp" if is_dev else "http://mcp-server:8001/mcp"
            self.mcp_server_url = os.getenv("MCP_SERVER_URL", default_url)

        logger.info(f"🚀 [Harness] 预备连接至 MCP 服务器: {self.mcp_server_url}")

        self.loop = asyncio.new_event_loop()
        self.agent_core: PipelineMultiAgentSystem | None = None
        self._thread: threading.Thread | None = None
        
        # 资源栈与 Client
        self._exit_stack = AsyncExitStack()
        self.client: Client | None = None

        # Trace 处理器
        self.langfuse_handler = CallbackHandler()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()

    async def _async_init(self) -> None:
        """在背景 Loop 中打通网络管道，自动转换并装载内核工具"""
        lc_tools: list[BaseTool] = []
        try:
            logger.info(f"🔄 [Harness] 正在建立 FastMCP 连接: {self.mcp_server_url}")

            # 1. 初始化 Client
            self.client = Client(self.mcp_server_url)

            # 2. 优雅使用 AsyncExitStack 管理 Context
            await self._exit_stack.enter_async_context(self.client)
            logger.info("✨ [Harness] MCP 网络管道打通成功！")

            # 3. 转换 MCP 工具为 LangChain 工具
            if self.client.session:
                lc_tools = await load_mcp_tools(self.client.session)
            else:
                raise RuntimeError("FastMCP Session 未成功建立，无法加载工具")

            logger.info(f"✅ [Harness] 成功自动转换并装载 {len(lc_tools)} 个 LangChain 工具")

        except Exception as e:
            logger.error(f"❌ [Harness] MCP 管道建立失败: {e}", exc_info=True)
            # 💡 最佳实践：不允许带病启动，必须向上抛出异常阻止初始化成功
            raise RuntimeError(f"Harness 初始化失败，无法连接 MCP 服务器: {e}") from e

        # 4. 构建 Agent 核心
        self.agent_core = PipelineMultiAgentSystem(mcp_tools=lc_tools)

    def bootstrap(self, timeout: float = 60.0) -> None:
        """启动 Harness 背景线程并同步等待初始化完成"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="HarnessLoopThread")
        self._thread.start()

        # 将初始化协程投递到后台 Loop 执行
        future = asyncio.run_coroutine_threadsafe(self._async_init(), self.loop)
        
        try:
            future.result(timeout=timeout)
        except Exception as e:
            logger.critical(f"💥 [Harness] Bootstrap 初始化超时或失败: {e}")
            self.shutdown()
            raise e

    # 为了防止开发人员不小心在 self.loop 线程内部误调 interact() 导致死锁，或者避免 future.result() 无限期挂起，加上线程检查和超时控制：
    # 給 Streamlit / CLI 脚本等纯同步代码用
    def interact(self, user_message: str, thread_id: str, timeout: float = 60.0) -> str:
        """同步阻塞交互接口（Facade 模式）"""
        if not self.agent_core:
            raise RuntimeError("Harness 运行壳尚未就绪！")

        # 🚨 防死锁检查：禁止在 Harness 自己的事件循环线程中直接调用同步阻塞接口
        try:
            current_loop = asyncio.get_running_loop()
            if current_loop is self.loop:
                raise RuntimeError(
                    "❌ 严禁在 Harness 事件循环线程内部调用同步 interact()！"
                    "这会导致死锁，请使用异步 API 或在独立线程中调用。"
                )
        except RuntimeError:
            # 如果当前没有运行中的 loop（说明处于纯同步线程），属于安全环境，忽略报错
            pass

        inputs = {"messages": [("user", user_message)]}
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [self.langfuse_handler],
        }

        async def _call_wrapper():
            return await self.agent_core.ainvoke(inputs, config)

        future = asyncio.run_coroutine_threadsafe(_call_wrapper(), self.loop)
        
        # 💡 加上 timeout，哪怕 LLM 卡死或网络卡住，也能抛出 TimeoutError，避免服务无休止挂起
        try:
            result = future.result(timeout=timeout)
            return result["messages"][-1].content
        except (TimeoutError, asyncio.TimeoutError):
            logger.error(f"⏱️ [interact] 执行超时 ({timeout}s)")
            raise TimeoutError("Agent 响应超时，请稍后重试。")

    # 給 FastAPI 的异步路由（Async Route）用
    # 职责：解决跨两个事件循环（FastAPI 主 Loop $\leftrightarrow$ Harness 后台 Loop）的数据安全传递。
    # 本质：是一个 AsyncGenerator（异步生成器），必须用 async for 配合 await 消费。
    async def interact_stream(self, user_message: str, thread_id: str) -> AsyncGenerator[str, None]:
        """
        专供 FastAPI 调用的异步流式接口
        💡 关键修复：使用 janus 或标准 asyncio.Queue + loop.call_soon_threadsafe 避免跨线程 Queue 死锁
        """
        if not self.agent_core:
            raise RuntimeError("Harness 运行壳尚未就绪！")

        inputs = {"messages": [("user", user_message)]}
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [self.langfuse_handler],
        }

        # -------------------------------------------------------------
        # 1. 【主线程 / 班长 / 消费者】
        # 获取当前 FastAPI 主线程的 Loop，并在这个 Loop 里创建队列
        # -------------------------------------------------------------
        main_loop = asyncio.get_running_loop()
        main_q: asyncio.Queue = asyncio.Queue()

        # -------------------------------------------------------------
        # 2. 【核心线程同步桥梁 / 传纸条的交警】
        # 这是一个辅助函数，用来把数据安全地投递给主线程
        # -------------------------------------------------------------
        def _safe_put(item: Any):
            # 💡 call_soon_threadsafe 就是 Python 提供的“跨线程同步机制”！
            # 它的意思是：“Loop A（主线程），请在你下一次打拍子（Tick）的时候，
            # 执行 main_q.put_nowait(item)”
            # 【后台线程 Loop B】
            #     │
            #     │ 1. 并不直接修改 main_q！
            #     │ 2. 而是向主线程 Loop A 的 OS 自定义信号管道（Self-Pipe / EventFD）发送一个字节的通知
            #     ▼
            # ┌─────────────────────────────────────────┐
            # │       主线程 Loop A 的 Selector (epoll) │ ◄── 3. 主线程的 CPU 被 OS 硬件中断唤醒！
            # └─────────────────────────────────────────┘
            #     │
            #     │ 4. 主线程在【自己的线程内】安全执行 main_q.put_nowait()
            #     ▼
            # ┌─────────────────────────────────────────┐
            # │     main_q 内部安全的 set_result()     │
            # └─────────────────────────────────────────┘
            #     │
            #     │ 5. 主线程唤醒 get()，成功拿到数据！
            main_loop.call_soon_threadsafe(main_q.put_nowait, item)

        # -------------------------------------------------------------
        # 3. 【后台线程 / 学习委员 / 生产者】
        # 这个 producer 协程会被扔到后台 Harness 线程（Loop B）去跑
        # -------------------------------------------------------------
        async def producer():
            try:
                async for chunk in self.agent_core.astream(inputs, config, stream_mode="updates"):
                    payload =_extract_stream_payload(chunk)
                    if payload:
                        _safe_put(payload)
            except BaseException as e:  # 使用 BaseException 确保 CancelledError 或极罕见异常也能捕获
                    logger.error(f"❌ [Producer] 节点执行异常: {e}", exc_info=True)
                    _safe_put(e)
            finally:
                _safe_put(None)  # 生产结束，放一个 None 代表“打烊了”

        # 将 producer 扔到 Harness 背景 Loop 执行
        asyncio.run_coroutine_threadsafe(producer(), self.loop)

        # -------------------------------------------------------------
        # 4. 【主线程 / 消费者吃数据】
        # 消费者在 Loop A 里安全地从自己的队列里拿数据
        # -------------------------------------------------------------
        while True:
            item = await main_q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    # 职责：解决同步线程与后台事件循环（Streamlit 纯同步线程 ↔ Harness 后台 Loop）的数据安全传递。
    # 本质：是一个标准 Generator（同步生成器），直接用普通的 for 循环或 yield 消费，依靠 queue.Queue.get() 的阻塞特性来等数据。
    def interact_stream_sync(self, user_message: str, thread_id: str) -> Generator[str, None, None]:
        """专供 Streamlit / CLI 调用的同步流式接口（使用标准 queue.Queue 跨线程安全通信）"""
        if not self.agent_core:
            raise RuntimeError("Harness 运行壳尚未就绪！")

        sync_q: queue.Queue = queue.Queue()
        inputs = {"messages": [("user", user_message)]}
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [self.langfuse_handler],
        }

        async def _async_producer():
            try:
                # 💡 直接在背景 Loop 中消费 astream，并将结果塞入同步队列
                async for chunk in self.agent_core.astream(inputs, config, stream_mode="updates"):
                    payload = _extract_stream_payload(chunk)
                    if payload:
                        sync_q.put(payload)
            except Exception as e:
                logger.error(f"❌ [Sync Producer] 执行异常: {e}", exc_info=True)
                sync_q.put(e)
            finally:
                sync_q.put(None)

        # 投递到 Harness 背景 Loop 执行
        asyncio.run_coroutine_threadsafe(_async_producer(), self.loop)

        while True:
            item = sync_q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def shutdown(self) -> None:
        """优雅停机：安全关闭 MCP 资源与背景事件循环"""
        logger.info("🛑 [Harness] 正在优雅关闭 Harness 资源...")

        # 1. 在背景 Loop 中关闭 AsyncExitStack (包含 FastMCP 连接)
        if self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._exit_stack.aclose(), self.loop)
            try:
                future.result(timeout=10)
            except Exception as e:
                logger.error(f"⚠️ [Harness] 关闭 AsyncExitStack 异常: {e}")

            # 2. 停止事件循环
            self.loop.call_soon_threadsafe(self.loop.stop)

        # 3. 等待后台线程退出
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        logger.info("👋 [Harness] 资源已完全释放。")