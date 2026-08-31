from typing import Any, AsyncGenerator, Dict, Sequence
from typing_extensions import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.core.llm_router import router
from src.core.shop_agent.prompts import SHOP_SYSTEM_PROMPT
from src.core.shop_agent.tools import add_device, query_shop_data, sell_device
from src.core.voyager_agent.skill_library import SkillLibrary
from src.core.voyager_agent.voyager_strategy import CustomSandboxVoyagerStrategy
from ..strategies.base import BaseAgentStrategy


class ShopState(TypedDict):
  messages: Annotated[list, add_messages]


class ShopAgentStrategy(BaseAgentStrategy):
  """手機店 Agent 策略實現（整合 Voyager 技能演進）"""

  def __init__(self, skill_library: SkillLibrary | None = None):
    super().__init__()
    self.graph = None
    self.llm = None
    self.skill_library = skill_library

  def _create_voyager_tool(self) -> BaseTool:
    """創建驅動自定義沙盒 (Subprocess) + Voyager 探索與技能演進的工具"""

    @tool
    async def execute_voyager_task(task_description: str) -> str:
      """當遇到複雜數據處理、自動化腳本生成、未知業務流程分析或需要自動編程解決的任務時調用此工具。

      此工具會在子程序沙盒中自動探索、編寫代碼、驗證並積累技能至資料庫。
      """
      if not self.skill_library:
        return "錯誤：系統未初始化 Voyager 技能庫。"

      try:
        # 1. 傳入原始未綁定工具的 router LLM，避免子流程產生非預期的 Tool Calling
        from src.core.llm_router import router as base_llm

        # 2. 實例化 CustomSandboxVoyagerStrategy 策略子圖
        voyager = CustomSandboxVoyagerStrategy(self.skill_library, base_llm)
        voyager_graph = voyager.build_graph()

        # 3. 異步觸發 Voyager 狀態機圖
        result = await voyager_graph.ainvoke({"task": task_description})

        # 4. 解析子圖執行的結果並返回給主控 ShopAgent
        if result.get("success"):
          return (
              f"✅ Voyager 任務執行成功並已歸檔技能！\n"
              f"【執行輸出】:\n{result.get('execution_result')}\n"
              f"【生成的技能代碼】:\n```python\n{result.get('generated_code')}\n```"
          )
        else:
          return (
              f"❌ Voyager 任務執行失敗。\n"
              f"重試次數: {result.get('retry_count')}\n"
              f"錯誤日誌: {result.get('error_log')}"
          )
      except Exception as e:
        return f"執行 Voyager 技能演進時發生系統例外錯誤: {str(e)}"

    return execute_voyager_task

  def _extract_staff_info(self, config: RunnableConfig) -> Dict[str, str]:
    configurable = config.get("configurable", {})
    current_staff = configurable.get("current_staff", {})
    shop_id = configurable.get("shop_id", "未知店鋪")
    role = configurable.get("role", "店員")

    def _get(obj, key, default=None):
      if isinstance(obj, dict):
        return obj.get(key, default)
      return getattr(obj, key, default)

    user_id = _get(current_staff, "id") or _get(
        current_staff, "user_id", "1001"
    )
    user_name = _get(current_staff, "name") or _get(
        current_staff, "user_name", "未知員工"
    )
    shop_obj = _get(current_staff, "shop", {})
    store_name = (
        _get(shop_obj, "name") if shop_obj else f"店鋪 ({shop_id})"
    )

    return {
        "user_id": str(user_id),
        "user_name": str(user_name),
        "role": str(role),
        "store_name": str(store_name),
    }

  def _create_graph_structure_tool(self) -> BaseTool:

    @tool
    def get_system_graph_structure() -> str:
      """當用戶詢問系統的邏輯圖、節點架構、LangGraph 圖結構或工作流時調用此工具。"""
      if not self.graph:
        return "系統圖未生成"
      try:
        mermaid_syntax = self.graph.get_graph().draw_mermaid()
        return f"```mermaid\n{mermaid_syntax}\n```"
      except Exception as e:
        return f"獲取系統圖失敗: {str(e)}"

    return get_system_graph_structure

  def build(
      self,
      mcp_tools: Sequence[BaseTool],
      checkpointer: BaseCheckpointSaver | None = None,
  ) -> None:
    graph_structure_tool = self._create_graph_structure_tool()
    voyager_tool = self._create_voyager_tool()

    # 合併本地業務工具、Voyager 工具與 MCP 工具
    local_tools = [
        add_device,
        sell_device,
        query_shop_data,
        graph_structure_tool,
        voyager_tool,
    ]
    all_tools = local_tools + list(mcp_tools)

    tool_node = ToolNode(all_tools, handle_tool_errors=True)
    self.llm = router.bind_tools(all_tools)

    def _agent_node(state: ShopState, config: RunnableConfig):
      staff_info = self._extract_staff_info(config)
      dynamic_system_prompt = SHOP_SYSTEM_PROMPT.format(**staff_info)

      input_messages = self.prepare_input_messages(
          raw_messages=state["messages"],
          system_prompt=dynamic_system_prompt,
          llm=self.llm,
          max_tokens=4000,
      )
      response = self.llm.invoke(input_messages, config=config)
      return {"messages": [response]}

    graph_builder = StateGraph(ShopState)
    graph_builder.add_node("agent", _agent_node)
    graph_builder.add_node("tools", tool_node)

    graph_builder.add_edge(START, "agent")

    def route_condition(state: ShopState):
      last_msg = state["messages"][-1]
      if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
      return END

    graph_builder.add_conditional_edges(
        "agent", route_condition, {"tools": "tools", END: END}
    )
    graph_builder.add_edge("tools", "agent")

    saver = checkpointer if checkpointer is not None else MemorySaver()
    self.graph = graph_builder.compile(checkpointer=saver)

  async def ainvoke(
      self, inputs: dict[str, Any], config: dict[str, Any]
  ) -> dict[str, Any]:
    self._check_built()
    return await self.graph.ainvoke(inputs, config=config)

  async def astream(
      self,
      inputs: dict[str, Any],
      config: dict[str, Any],
      stream_mode: str = "updates",
  ) -> AsyncGenerator[dict[str, Any], None]:
    self._check_built()
    async for chunk in self.graph.astream(
        inputs, config=config, stream_mode=stream_mode
    ):
      yield chunk

  def _check_built(self) -> None:
    if not self.graph:
      raise RuntimeError(
          f"{self.__class__.__name__} 尚未調用 build() 完成構建！"
      )