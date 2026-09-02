import json
import os
import re
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

# 引入現有的組件模組
from src.core.voyager_agent.run_tests import run_tests  # 本地隔離測試 runner
from src.github.submit_tool import (  # GitHub 模組
    FileChange,
    get_file_content,
    submit_code_change,
)
from .skill_library import SkillLibrary  # Voyager Vector DB & 本地存儲


class VoyagerAgentOrchestrator:

  def __init__(
      self,
      owner: str,
      repo: str,
      supabase_url: str,
      supabase_key: str,
      gemini_api_key: str,
      base_branch: str = "main",
  ):
    self.owner = owner
    self.repo = repo
    self.base_branch = base_branch

    # 1. 初始化 SkillLibrary
    self.skill_lib = SkillLibrary(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        gemini_api_key=gemini_api_key,
    )
    # 2. 初始化 Gemini AI Client
    self.ai_client = genai.Client(api_key=gemini_api_key)

  def fix_bug_or_add_feature(
      self,
      task_description: str,
      target_file_path: Optional[str] = None,
      test_file_path: Optional[str] = None,
      max_retries: int = 3,
  ) -> Dict[str, Any]:
    """Agent 主循環：

    讀取 Context -> LLM 編寫修改代碼 -> 本地 pytest 沙盒 -> 成功則存入 Skill DB & GitHub
    開 PR
    """
    existing_code = ""
    existing_test = ""

    # 第一步：如果涉及修改現有代碼，先使用 get_file_content 提取 Context
    if target_file_path:
      try:
        existing_code = get_file_content(
            owner=self.owner,
            repo=self.repo,
            path=target_file_path,
            ref=self.base_branch,
        )
        print(f"📖 成功讀取現有代碼檔案: {target_file_path}")
      except FileNotFoundError:
        print(f"ℹ️ 檔案 {target_file_path} 不存在，將走「新建模式」。")

    if test_file_path:
      try:
        existing_test = get_file_content(
            owner=self.owner,
            repo=self.repo,
            path=test_file_path,
            ref=self.base_branch,
        )
      except FileNotFoundError:
        pass

    # 檢索 Skill DB 尋找類似的經驗片段
    related_skills = self.skill_lib.retrieve_skills(task_description, top_k=2)

    # 抽離 JSON Schema 格式要求，避免 f-string 解析問題
    json_schema_instruction = """{
    "skill_name": "簡短技能標示符",
    "description": "功能或修改的簡要描述",
    "target_file_path": "目標工具檔案在 repo 中的相對路徑",
    "test_file_path": "對應測試檔案在 repo 中的相對路徑",
    "tool_code": "工具完整的 Python 原始碼",
    "test_code": "完整的 pytest 測試原始碼"
}"""

    formatted_skills = json.dumps(
        related_skills, ensure_ascii=False, indent=2
    )
    target_path_str = (
        target_file_path
        or "未指定，請自行建議路徑（例：src/core/voyager_agent/skills_storage/my_skill.py）"
    )
    code_str = existing_code if existing_code else "# 新檔案，暫無現有代碼"
    test_str = existing_test if existing_test else "# 新檔案，暫無現有測試"

    prompt_context = f"""你是一個具備修代碼和自我測試能力的 Voyager AI Agent。

【任務描述】
{task_description}

【現有參考技能 (Vector DB Search)】
{formatted_skills}

【目標工具檔案路徑】: {target_path_str}
【當前現有工具代碼】:
{code_str}

【當前現有測試代碼】:
{test_str}

【約束要求】:
1. 在 test_code 中引用工具時，**必須使用 `from tool import ...`**（因為測試將在臨時沙盒環境中運行，工具模組名固定為 tool）。
2. 如果是修改現有的代碼/修 Bug，必須輸出修正後的**完整代碼**，不要給省略號。
3. 如果任務涉及字串處理或回文判斷（Palindrome），請確保保留字母與數字 (alphanumeric, 使用 `c.isalnum()` 或 `[^a-zA-Z0-9]`)，切勿將數字誤刪。
4. 請確保輸出的 JSON 格式完全合法。程式碼中的換行請統一使用標準 JSON 字串轉義（`\\n`），切勿包含未轉義的控制字元。
5. 請嚴格輸出 JSON 格式，結構如下：
{json_schema_instruction}
"""

    error_feedback = ""

    # 第二步：迭代思考與 self-correction 循環
    for attempt in range(1, max_retries + 1):
      print(
          f"\n🔄 [Attempt {attempt}/{max_retries}] 正在請求 LLM"
          " 生成/重構代碼..."
      )

      current_prompt = prompt_context
      if error_feedback:
        current_prompt += (
            f"\n\n⚠️ 【上一輪測試失敗的錯誤日誌】：\n{error_feedback}\n請分析上述報錯原因，並修復代碼與測試。"
        )

      response = self.ai_client.models.generate_content(
          model="gemini-3.5-flash",
          contents=current_prompt,
          config=types.GenerateContentConfig(
            # 配置 AFC 自動調用工具的上限
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False,
                maximum_remote_calls=5,  # 👈 預設通常是 10，建議改成 3 ~ 5 避免超時
            ),
            response_mime_type="application/json"
          ),
      )

      # ---------------- 清洗 Markdown 標記與增強 JSON 解析 ----------------
      raw_text = response.text.strip() if response.text else ""
      clean_text = re.sub(
          r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE
      ).strip()

      try:
        res_data = json.loads(clean_text, strict=False)
      except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失敗，LLM 原始輸出內容如下：\n{raw_text}")
        raise ValueError(f"LLM 輸出的 JSON 格式無效: {e}")
      # ------------------------------------------------------------------

      tool_code = res_data["tool_code"]
      test_code = res_data["test_code"]
      skill_name = res_data["skill_name"]
      rel_tool_path = (
          res_data.get("target_file_path")
          or target_file_path
          or f"src/core/voyager_agent/skills_storage/{skill_name}.py"
      )
      rel_test_path = (
          res_data.get("test_file_path")
          or test_file_path
          or f"test/skills/test_{skill_name}.py"
      )

      # 第三步：運行本地臨時沙盒測試
      print("🧪 在臨時 subprocess 沙盒中執行 pytest...")
      test_res = run_tests(tool_code=tool_code, test_code=test_code)

      if test_res.passed:
        print("✅ 沙盒測試完全通過！")

        # 第四步 A：保存到 Supabase 向量庫 & 本地技能檔案
        print("💾 正在將新/改動的技能寫入 SkillLibrary (Supabase)...")
        self.skill_lib.add_skill(
            name=skill_name,
            description=res_data["description"],
            code=tool_code,
        )

        # 第四步 B：提交至 GitHub 並建立 Pull Request
        print("🚀 正在提交代碼變更並拉取 GitHub Pull Request...")
        files_to_commit = [
            FileChange(
                path=rel_tool_path,
                content=tool_code,
                commit_message=f"feat(agent): update/create tool {skill_name}",
            ),
            FileChange(
                path=rel_test_path,
                content=test_code,
                commit_message=(
                    f"test(agent): update/create unit test for {skill_name}"
                ),
            ),
        ]

        pr = submit_code_change(
            owner=self.owner,
            repo=self.repo,
            change_id=skill_name,
            files=files_to_commit,
            base_branch=self.base_branch,
            pr_title=f"[Agent Auto-Skill] {skill_name}",
            pr_body=(
                f"## 🤖 Voyager Agent 代碼自動變更說明\n\n"
                f"**任務背景**: {task_description}\n\n"
                f"**修改檔案**:\n"
                f"- `{rel_tool_path}`\n"
                f"- `{rel_test_path}`\n\n"
                f"### 本地沙盒測試結果:\n```text\n{test_res.output}\n```"
            ),
        )

        print(f"🎉 PR 創建成功！連結：{pr.html_url}")
        return {
            "status": "success",
            "pr_url": pr.html_url,
            "pr_number": pr.number,
            "skill_name": skill_name,
            "test_output": test_res.output,
        }
      else:
        print(
            f"❌ 第 {attempt} 次測試未通過，捕獲錯誤資訊給 LLM 修正..."
        )
        error_feedback = test_res.output

    raise RuntimeError(
        f"Agent 在 {max_retries} 次嘗試後仍未能修正代碼，測試日誌：\n{error_feedback}"
    )