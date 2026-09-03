
import os
import re
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from src.core.voyager_agent.build_llm_context import VOYAGER_CODE_REPAIR_TOOLS
from src.core.voyager_agent.prompt import VOYAGER_SYSTEM_PROMPT, build_feedback_prompt
from src.core.voyager_agent.skill_library import SkillLibrary
from src.core.voyager_agent.sandbox import run_tests_with_ast_check
from src.core.voyager_agent.run_tests import check_code_safety, RUNTIME_SECURITY_HEADER, save_to_pending_store


# 1. VoyagerState 定义
class VoyagerState(TypedDict):
    task: str
    target_file: Optional[str]  # 修復目標檔案路徑
    retrieved_skills: str
    generated_code: str
    execution_result: str
    error_log: str
    retry_count: int
    success: bool


class SkillCustomSandboxVoyagerStrategy:
    """基於輕量子程序 (Subprocess) 自定義沙盒與 Tool Binding 的 Code Repair / Voyager 演進策略"""

    def __init__(
        self,
        skill_library: SkillLibrary,
        llm: Any,
        repair_tools: Optional[List[Any]] = VOYAGER_CODE_REPAIR_TOOLS,
        max_retries: int = 3,
    ):
        self.skill_library = skill_library
        self.llm = llm
        self.max_retries = max_retries

        self.repair_tools = repair_tools or []
        if self.repair_tools:
            self.llm_with_tools = self.llm.bind_tools(self.repair_tools)
        else:
            self.llm_with_tools = self.llm

    def build_graph(self):
        builder = StateGraph(VoyagerState)

        # 1. 檢索歷史修復經驗/相關技能
        def retrieve_node(state: VoyagerState):
            skills_data = self.skill_library.retrieve_skills(state["task"])

            skills_formatted = "\n\n".join([
                f"--- 參考經驗: {s.get('name')} ---\n描述: {s.get('description')}\n代碼:\n{s.get('code', '')}"
                for s in skills_data
            ])

            return {
                "target_file": state.get("target_file", "src/service/discount.py"),
                "retrieved_skills": (
                    skills_formatted if skills_formatted else "（目前無相關修復經驗）"
                ),
                "retry_count": state.get("retry_count", 0),
                "error_log": state.get("error_log", ""),
                "generated_code": state.get("generated_code", ""),
            }

        # 2. 生成/修正修復代碼
        def code_act_node(state: VoyagerState):
            error_log = state.get("error_log", "")
            last_code = state.get("generated_code", "")
            target_file = state.get("target_file", "未指定檔案")

            # 动态生成 Feedback Prompt
            feedback_prompt = build_feedback_prompt(error_log, last_code)

            # 使用组件导入的 VOYAGER_SYSTEM_PROMPT 进行格式化
            prompt = VOYAGER_SYSTEM_PROMPT.format(
                target_file=target_file,
                task=state["task"],
                retrieved_skills=state["retrieved_skills"],
                feedback_prompt=feedback_prompt,
            )

            response = self.llm_with_tools.invoke(prompt)

            raw_content = ""
            if hasattr(response, "content"):
                if isinstance(response.content, str):
                    raw_content = response.content
                elif isinstance(response.content, list) and len(response.content) > 0:
                    first_item = response.content[0]
                    if isinstance(first_item, dict):
                        raw_content = first_item.get("text", "")
                    else:
                        raw_content = str(first_item)

            # 如果 response 觸發了 tool_calls 但 content 為空，改用無 Tool 的 LLM 強制要求產生 Code
            if not raw_content.strip() and hasattr(response, "tool_calls") and response.tool_calls:
                fallback_response = self.llm.invoke(
                    prompt + "\n注意：請直接輸出修復後的 Python 代碼，不要呼叫工具，嚴禁使用 input()。"
                )
                raw_content = (
                    fallback_response.content
                    if hasattr(fallback_response, "content")
                    else str(fallback_response)
                )

            cleaned_code = re.sub(
                r"^```(?:python)?\s*\n|```$", "", str(raw_content).strip(), flags=re.MULTILINE
            ).strip()

            return {"generated_code": cleaned_code}

        # 3. 沙盒測試執行
        def sandbox_execution_node(state: VoyagerState):
            code = state.get("generated_code", "").strip()

            if not code:
                return {
                    "generated_code": "",
                    "error_log": "Runtime Error:\nLLM 未生成任何有效的程式碼（代碼為空）。",
                    "execution_result": "",
                    "success": False,
                    "retry_count": state.get("retry_count", 0) + 1,
                }

            # 💡 [Step 1] 静态 AST 安全拦截
            security_error = check_code_safety(code)
            if security_error:
                return {
                    "generated_code": code,
                    "error_log": f"Security Violation Error:\n{security_error}\n請重新設計代碼，不要引入被禁止的模組或函數。",
                    "execution_result": "",
                    "success": False,
                    "retry_count": state.get("retry_count", 0) + 1,
                }

            # 💡 [Step 2] 动态安全 Hook 拼接 (包含 input 拦截与文件删除限制)
            full_executable_code = RUNTIME_SECURITY_HEADER + code

            tmp_fd, tmp_file_path = tempfile.mkstemp(suffix=".py", text=True)
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
                    tmp_file.write(full_executable_code)

                result = subprocess.run(
                    [sys.executable, tmp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                if result.returncode == 0:
                    stdout_msg = result.stdout.strip() or "✅ 所有單元測試與 assert 斷言皆順利通過！"
                    return {
                        "generated_code": code,  # 状态库只保存 LLM 生成的原生干净代码
                        "execution_result": stdout_msg,
                        "success": True,
                        "error_log": "",
                    }
                else:
                    error_msg = (
                        result.stderr.strip() or result.stdout.strip() or "未知運行錯誤"
                    )
                    return {
                        "generated_code": code,
                        "error_log": f"Runtime Error:\n{error_msg}",
                        "execution_result": "",
                        "success": False,
                        "retry_count": state.get("retry_count", 0) + 1,
                    }
            except subprocess.TimeoutExpired:
                return {
                    "generated_code": code,
                    "error_log": "Execution Error: 程式執行超過 15 秒限制，可能存在死循環。",
                    "execution_result": "",
                    "success": False,
                    "retry_count": state.get("retry_count", 0) + 1,
                }
            except Exception as e:
                return {
                    "generated_code": code,
                    "error_log": f"Execution Exception: {str(e)}",
                    "execution_result": "",
                    "success": False,
                    "retry_count": state.get("retry_count", 0) + 1,
                }
            finally:
                if os.path.exists(tmp_file_path):
                    try:
                        os.remove(tmp_file_path)
                    except OSError:
                        pass

        # 4. 生成 Patch 單並寫入待審核暫存區
        def archive_skill_node(state: VoyagerState):
            review_id = f"patch_{uuid.uuid4().hex[:8]}"
            target_file = state.get("target_file") or "src/service/discount.py"
            fixed_code = state.get("generated_code", "")
            exec_result = state.get("execution_result", "")

            patch_item = {
                "review_id": review_id,
                "target_file": target_file,
                "issue_description": state.get("task", ""),
                "status": "PENDING_REVIEW",
                "fixed_code": fixed_code,
                "execution_result": exec_result,
                "retry_count": state.get("retry_count", 0),
            }

            save_to_pending_store(patch_item)

            print(
                f"\n🎉 [沙盒測試通過] 已成功生成修復單 Patch！(Review ID: {review_id}, 目標檔案: {target_file})"
            )
            return {
                "generated_code": fixed_code,
                "execution_result": exec_result,
            }

        # 構建 StateGraph
        builder.add_node("retrieve", retrieve_node)
        builder.add_node("code_act", code_act_node)
        builder.add_node("execute", sandbox_execution_node)
        builder.add_node("archive", archive_skill_node)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "code_act")
        builder.add_edge("code_act", "execute")

        def route_after_execution(state: VoyagerState):
            if state["success"]:
                return "archive"
            if state["retry_count"] < self.max_retries:
                return "code_act"
            return END

        builder.add_conditional_edges(
            "execute",
            route_after_execution,
            {"archive": "archive", "code_act": "code_act", END: END},
        )
        builder.add_edge("archive", END)

        return builder.compile()