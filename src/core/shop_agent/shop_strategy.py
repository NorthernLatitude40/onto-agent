import json
import uuid
import redis
import traceback
import modal
from typing import Any, AsyncGenerator, Dict, List, Sequence
from typing_extensions import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool, tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from src.common.database_restful import supabase

from src.core.llm_router import router
from src.core.shop_agent.prompts import SHOP_SYSTEM_PROMPT
from src.core.shop_agent.tools import add_device, query_shop_data, sell_device
from src.core.voyager_agent.skill_library import SkillLibrary
from ..strategies.base import BaseAgentStrategy
from src.common.redis_client import redis_client

class ShopState(TypedDict):
    messages: Annotated[list, add_messages]


class ShopAgentStrategy(BaseAgentStrategy):
    """手機店 Agent 策略實現（整合 SkillLibrary + Redis 異步 Voyager 演進）"""

    def __init__(self, redis_conn: redis.Redis = None):
        super().__init__()
        self.graph = None
        self.llm = None
        self.skill_library: SkillLibrary | None = None
        # 初始化 Redis 連接
        # 使用统一的 redis_client
        self.redis = redis_conn or redis_client

    def _load_skills_as_tools(self) -> List[BaseTool]:
        """從 SkillLibrary 中動態加載所有已歸檔技能並轉換為 LLM 工具"""
        if not self.skill_library:
            return []

        skill_tools: List[BaseTool] = []
        try:
            # ✅ 改為正確從 SkillLibrary 獲取技能列表的方法
            skills = self.skill_library.get_all_skills()  # 或 self.skill_library.get_skills()
            
            for skill in skills:
                skill_name = skill.get("name")
                description = skill.get("description", "Voyager 演進技能")
                code_str = skill.get("code")

                if not code_str or not skill_name:
                    continue

                local_scope = {}
                exec(code_str, globals(), local_scope)
                func = local_scope.get(skill_name)

                if not func:
                    for obj in local_scope.values():
                        if callable(obj) and getattr(obj, "__name__", "") != "<lambda>":
                            func = obj
                            break

                if func:
                    dynamic_tool = StructuredTool.from_function(
                        func=func,
                        name=skill_name,
                        description=description,
                    )
                    skill_tools.append(dynamic_tool)
        except Exception as e:
            print(f"⚠️ [Skill Library] 加載技能工具失敗: {e}")

        return skill_tools

    def _create_voyager_queue_tool(self) -> BaseTool:
        """創建基於 Modal Serverless 的 Voyager 技能演進觸發工具"""

        @tool
        async def execute_voyager_task(task_description: str) -> str:
            """當用戶要求「編寫/創建新工具」、「新增計算邏輯（如二手估價、折舊計算）」或遇到未知業務邏輯時呼叫此工具。
            此工具會將技能開發任務直接觸發至 Modal Serverless Worker，由雲端容器在沙盒中進行代碼編寫、測試與歸檔。
            """
            try:
                # 1. 檢索 Supabase 看是否有重複技能
                data = None
                if self.skill_library:
                    data = self.skill_library.retrieve_skills(task_description)

                if data:
                    matched_skill = data[0]
                    return f"ℹ️ 檢測到已存在相似功能的技能 '{matched_skill['name']}'，無需重複生成。"

                # 2. 生成任務 ID 并初始化 Redis 狀態記錄 (TTL 1小時)
                task_id = f"voyager_task_{uuid.uuid4().hex[:8]}"
                
                if self.redis:
                    self.redis.hset(
                        f"voyager:status:{task_id}",
                        mapping={"status": "PENDING", "task": task_description},
                    )
                    self.redis.expire(f"voyager:status:{task_id}", 3600)

                # 3. 直接觸發 Modal Serverless 函數（替換原本的 lpush redis 隊列）
                try:
                    run_voyager_task = modal.Function.from_name("voyager-worker", "run_voyager_task")
                    # .spawn() 爲非阻塞的異步觸發，響應毫秒級，不會阻塞 FastAPI/LangGraph 主線程
                    call_id = run_voyager_task.spawn(task_id, task_description)
                    print(f"🚀 [ShopAgent] 已成功派發技能開發任務至 Modal Serverless Worker (Task ID: {task_id}, Call ID: {call_id})")
                except Exception as modal_err:
                    # 記錄 Modal 觸發失敗日誌
                    print(f"❌ [ShopAgent] 呼叫 Modal Function 失敗: {modal_err}")
                    if self.redis:
                        self.redis.hset(f"voyager:status:{task_id}", "status", "FAILED")
                    raise modal_err

                return (
                    f"✅ 新技能生成任務已成功提交至 Modal Serverless 雲端 Worker 處理！\n"
                    f"【任務 ID】: {task_id}\n"
                    f"【任務描述】: {task_description}\n"
                    f"Modal 雲端容器正在沙盒中編寫代碼并進行 pytest 測試。測試通過後技能將自動歸檔，下次請求即可生效。"
                )

            except Exception as e:
                # 印出完整堆疊軌跡以便在控制台調試
                traceback.print_exc()
                return f"提交 Voyager 技能演進任務至 Modal 失敗: {str(e)}"

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
            """當用戶詢問系統的邏輯圖、節點架構或 LangGraph 圖結構時調用此工具。"""
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
        skill_library: SkillLibrary = None,
    ) -> None:
        self.skill_library = skill_library

        # 1. 加載已有 Skill 工具
        dynamic_skill_tools = self._load_skills_as_tools()

        # 2. 加載通用工具与 Redis 隊列觸發工具
        graph_structure_tool = self._create_graph_structure_tool()
        voyager_queue_tool = self._create_voyager_queue_tool()

        # 3. 組裝 Tool 集
        local_tools = [
            add_device,
            sell_device,
            query_shop_data,
            graph_structure_tool,
            voyager_queue_tool,
        ]
        all_tools = local_tools + dynamic_skill_tools + list(mcp_tools)

        tool_node = ToolNode(all_tools, handle_tool_errors=True)
        self.llm = router.bind_tools(all_tools)

        async def _agent_node(state: ShopState, config: RunnableConfig):
            staff_info = self._extract_staff_info(config)
            dynamic_system_prompt = SHOP_SYSTEM_PROMPT.format(**staff_info)

            input_messages = self.prepare_input_messages(
                raw_messages=state["messages"],
                system_prompt=dynamic_system_prompt,
                llm=self.llm,
                max_tokens=4000,
            )
            response = await self.llm.ainvoke(input_messages, config=config)
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
            raise RuntimeError(f"{self.__class__.__name__} 尚未調用 build()！")