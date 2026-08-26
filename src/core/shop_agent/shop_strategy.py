# src/core/strategies/shop_strategy.py
from typing import Any, AsyncGenerator, Sequence
from langchain_core.tools import BaseTool, tool
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

    def _create_graph_structure_tool(self) -> BaseTool:
        """动态生成绑定了 self.graph 的图架构查询工具（闭包模式）"""

        @tool
        def get_system_graph_structure() -> str:
            """当用户询问系统的逻辑图、节点架构、LangGraph 图结构或工作流时调用此工具。
            返回 Markdown Mermaid 格式的图结构字符串。
            """
            if not self.graph:
                return "系统图未生成"
            mermaid_syntax = self.graph.get_graph().draw_mermaid()
            return f"```mermaid\n{mermaid_syntax}\n```"

        return get_system_graph_structure

    def build(self, mcp_tools: Sequence[BaseTool]) -> None:
        # 1. 动态获取绑定的图拓扑 Tool
        graph_structure_tool = self._create_graph_structure_tool()

        # 2. 合并手机店自带的本地工具、图结构 Tool 与 MCP 工具
        local_tools = [add_device, sell_device, query_shop_data, graph_structure_tool]
        all_tools = local_tools + list(mcp_tools)
        
        tool_node = ToolNode(all_tools, handle_tool_errors=True)
        self.llm = router.bind_tools(all_tools)

        def _agent_node(state: ShopState, config: RunnableConfig):
            # 1. 从 RunnableConfig 的 configurable 字典中提取配置信息（带默认值兜底）
            configurable = config.get("configurable", {})
            current_staff = configurable.get("current_staff", {})
            shop_id = configurable.get("shop_id", "未知店铺")
            role = configurable.get("role", "店员")

            # 兼容 Pydantic 对象与 Dict 取值
            if isinstance(current_staff, dict):
                user_id = current_staff.get("id") or current_staff.get("user_id", "1001")
                user_name = current_staff.get("name") or current_staff.get("user_name", "未知员工")
                shop_obj = current_staff.get("shop", {})
                store_name = (shop_obj.get("name") if isinstance(shop_obj, dict) else getattr(shop_obj, "name", None)) or f"店铺 ({shop_id})"
            else:
                user_id = getattr(current_staff, "id", None) or getattr(current_staff, "user_id", "1001")
                user_name = getattr(current_staff, "name", None) or getattr(current_staff, "user_name", "未知员工")
                shop_obj = getattr(current_staff, "shop", None)
                store_name = getattr(shop_obj, "name", None) if shop_obj else f"店铺 ({shop_id})"

            # 2. 动态渲染 System Prompt 模板
            dynamic_system_prompt = SHOP_SYSTEM_PROMPT.format(
                user_id=user_id,
                user_name=user_name,
                role=role,
                store_name=store_name
            )

            # 💡 调用基类通用上下文治理方法：去除重复 SystemMessage + 按 Token 限额滑动截断
            input_messages = self.prepare_input_messages(
                raw_messages=state["messages"],
                system_prompt=dynamic_system_prompt,
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

        # 编译 StateGraph 存入 self.graph
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