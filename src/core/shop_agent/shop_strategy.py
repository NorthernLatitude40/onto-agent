# src/core/strategies/shop_strategy.py
from typing import Any, AsyncGenerator, Sequence
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict, Annotated

from src.core.llm_router import router
from src.core.shop_agent.prompts import SHOP_SYSTEM_PROMPT
from src.core.shop_agent.tools import add_device, sell_device, query_shop_data
from ..strategies.base import BaseAgentStrategy


class ShopState(TypedDict):
    messages: Annotated[list, add_messages]


class ShopAgentStrategy(BaseAgentStrategy):
    """手机店 Agent 策略实现"""

    def __init__(self):
        super().__init__()  # 初始化基类 context_cleaner
        self.graph = None
        self.llm = None

    def build(self, mcp_tools: Sequence[BaseTool]) -> None:
        # 合并手机店自带的本地工具和 MCP 工具
        local_tools = [add_device, sell_device, query_shop_data]
        all_tools = local_tools + list(mcp_tools)
        
        tool_node = ToolNode(all_tools, handle_tool_errors=True)
        self.llm = router.bind_tools(all_tools)

        def _agent_node(state: ShopState, config: RunnableConfig):
            # 💡 调用基类通用上下文治理方法：去除重复 SystemMessage + 按 Token 限额滑动截断
            input_messages = self.prepare_input_messages(
                raw_messages=state["messages"],
                system_prompt=SHOP_SYSTEM_PROMPT,
                llm=self.llm,
                max_tokens=4000,
            )
            response = self.llm.invoke(input_messages, config=config)
            return {"messages": [response]}

        # 构建 StateGraph
        graph_builder = StateGraph(ShopState)
        graph_builder.add_node("agent", _agent_node)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_edge(START, "agent")

        def route_condition(state: ShopState):
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                return "tools"
            return END

        graph_builder.add_conditional_edges("agent", route_condition, {"tools": "tools", END: END})
        graph_builder.add_edge("tools", "agent")

        # 编译 StateGraph
        self.graph = graph_builder.compile(checkpointer=MemorySaver())

    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        if not self.graph:
            raise RuntimeError("ShopAgentStrategy 尚未调用 build() 构建！")
        return await self.graph.ainvoke(inputs, config=config)

    async def astream(
        self, inputs: dict[str, Any], config: dict[str, Any], stream_mode: str = "updates"
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not self.graph:
            raise RuntimeError("ShopAgentStrategy 尚未调用 build() 构建！")
        async for chunk in self.graph.astream(inputs, config=config, stream_mode=stream_mode):
            yield chunk