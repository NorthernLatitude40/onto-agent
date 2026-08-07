import os
from typing import Annotated, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from src.core.llm_router import router
from src.core.shop_agent.prompts import SHOP_SYSTEM_PROMPT
from src.core.shop_agent.tools import add_device, query_stock, query_report, sell_device


class ShopState(TypedDict):
    messages: Annotated[list, add_messages]

class ShopAgentSystem:
    def __init__(self):
        # 手机店专用的工具库
        self.tools = [add_device, sell_device, query_stock, query_report]
        print("当前加载的工具名称:", [t.name for t in self.tools])
        self.tool_node = ToolNode(self.tools, handle_tool_errors=True)
        self.llm = router.bind_tools(self.tools)
        self.graph = self._build_graph()

    def _agent_node(self):
        def call(state: ShopState, config: RunnableConfig):
            messages = [("system", SHOP_SYSTEM_PROMPT)] + state["messages"]
            response = self.llm.invoke(messages, config=config)
            return {"messages": [response]}
        return call

    def _build_graph(self):
        graph = StateGraph(ShopState)
        graph.add_node("agent", self._agent_node())
        graph.add_node("tools", self.tool_node)

        graph.add_edge(START, "agent")

        def route_condition(state: ShopState):
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                return "tools"
            return END

        graph.add_conditional_edges("agent", route_condition, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")

        return graph.compile(checkpointer=MemorySaver())

    async def astream(self, inputs, config: dict):
        async for chunk in self.graph.astream(inputs, config=config, stream_mode="updates"):
            yield chunk