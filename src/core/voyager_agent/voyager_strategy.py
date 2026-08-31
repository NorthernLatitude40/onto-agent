import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from src.core.voyager_agent.skill_library import SkillLibrary


class VoyagerState(TypedDict):
  task: str
  retrieved_skills: str
  generated_code: str
  execution_result: str
  error_log: str
  retry_count: int
  success: bool


class CustomSandboxVoyagerStrategy:
  """基於輕量子程序 (Subprocess) 自定義沙盒的 Voyager 演進策略"""

  def __init__(
      self, skill_library: SkillLibrary, llm: Any, max_retries: int = 3
  ):
    self.skill_library = skill_library
    self.llm = llm
    self.max_retries = max_retries

  def build_graph(self):
    builder = StateGraph(VoyagerState)

    # 1. 檢索技能 (Skill Retrieval)
    def retrieve_node(state: VoyagerState):
      skills_data = self.skill_library.retrieve_skills(state["task"])
      # 整理成 LLM 易讀的格式
      skills_formatted = "\n\n".join([
          f"--- 技能: {s.get('name')} ---\n描述: {s.get('description')}\n代碼:\n{s.get('code', '')}"
          for s in skills_data
      ])
      return {
          "retrieved_skills": (
              skills_formatted if skills_formatted else "（目前無相符技能）"
          ),
          "retry_count": state.get("retry_count", 0),
      }

    # 2. 生成/修正代碼 (Code Generation / Iterative Refinement)
    def code_act_node(state: VoyagerState):
      prompt = f"""你是一個 Python 代碼生成專家。
任務: {state['task']}

可參考的已有技能庫:
{state['retrieved_skills']}

上一次執行報錯 (若有): {state.get('error_log', '無')}

請編寫獨立且可執行的 Python 代碼來完成任務。
【重要】僅返回純 Python 代碼，請勿包含 Markdown 標記（如 ```python ），確保代碼可以直接被 Python 解譯器執行。
"""
      response = self.llm.invoke(prompt)
      raw_content = response.content.strip()

      # 清理 Markdown 代碼區塊標記 (如 ```python ... ```)
      cleaned_code = re.sub(
          r"^```(?:python)?\n|\n```$", "", raw_content, flags=re.MULTILINE
      ).strip()

      return {"generated_code": cleaned_code}

    # 3. 自定義輕量沙盒執行 (Custom Subprocess Sandbox Execution)
    def sandbox_execution_node(state: VoyagerState):
      code = state["generated_code"]

      # 使用 Python 臨時檔案在隔離子程序中執行代碼
      with tempfile.NamedTemporaryFile(
          mode="w", suffix=".py", delete=False, encoding="utf-8"
      ) as tmp_file:
        tmp_file.write(code)
        tmp_file_path = tmp_file.name

      try:
        # 呼叫目前的 sys.executable 執行腳本，限制超時時間 15 秒預防死循環
        result = subprocess.run(
            [sys.executable, tmp_file_path],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
          return {
              "execution_result": result.stdout,
              "success": True,
              "error_log": "",
          }
        else:
          return {
              "error_log": result.stderr or result.stdout,
              "success": False,
              "retry_count": state["retry_count"] + 1,
          }
      except subprocess.TimeoutExpired:
        return {
            "error_log": "Execution Error: 程式執行超過 15 秒限制，可能存在死循環。",
            "success": False,
            "retry_count": state["retry_count"] + 1,
        }
      except Exception as e:
        return {
            "error_log": f"Execution Exception: {str(e)}",
            "success": False,
            "retry_count": state["retry_count"] + 1,
        }
      finally:
        # 清理臨時檔案
        if os.path.exists(tmp_file_path):
          os.remove(tmp_file_path)

    # 4. 技能提煉與保存 (Skill Archiving)
    def archive_skill_node(state: VoyagerState):
      prompt = f"""分析以下已成功執行的代碼，提煉出一個高複用性的 Python 函數技能：
代碼:
{state['generated_code']}

請僅返回標準 JSON 格式，格式如下：
{{
    "name": "snake_case_function_name",
    "description": "詳細功能說明"
}}
"""
      response = self.llm.invoke(prompt)
      content = response.content.strip()

      # 解析 JSON
      try:
        # 濾除 Markdown code block 標籤
        clean_json = re.sub(
            r"^```(?:json)?\n|\n```$", "", content, flags=re.MULTILINE
        ).strip()
        data = json.loads(clean_json)
        skill_name = data.get(
            "name", f"auto_skill_{re.sub(r'[^a-zA-Z0-9]', '_', state['task'][:10])}"
        )
        skill_desc = data.get("description", state["task"])
      except Exception:
        # 解析失敗時的回退機制 (Fallback)
        skill_name = (
            f"auto_skill_{re.sub(r'[^a-zA-Z0-9]', '_', state['task'][:10])}"
        )
        skill_desc = state["task"]

      # 使用新的 SkillLibrary 保存至 Supabase (資料庫包含 code 欄位)
      self.skill_library.add_skill(
          name=skill_name, description=skill_desc, code=state["generated_code"]
      )
      return {}

    # 構建 StateGraph
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("code_act", code_act_node)
    builder.add_node("execute", sandbox_execution_node)
    builder.add_node("archive", archive_skill_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "code_act")
    builder.add_edge("code_act", "execute")

    # 自自我修正條件路由 (Self-Correction Loop)
    def route_after_execution(state: VoyagerState):
      if state["success"]:
        return "archive"
      if state["retry_count"] < self.max_retries:
        return "code_act"  # 觸發自我修正機制重新生成 Code
      return END

    builder.add_conditional_edges(
        "execute",
        route_after_execution,
        {"archive": "archive", "code_act": "code_act", END: END},
    )
    builder.add_edge("archive", END)

    return builder.compile()