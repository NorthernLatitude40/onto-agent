import os
import re
from dotenv import load_dotenv

load_dotenv()

from src.core.llm_router import router
from src.core.voyager_agent.skill_library import SkillLibrary
from core.voyager_agent.skill_generation_strategy import CustomSandboxVoyagerStrategy
from src.scripts.apply_patch import apply_patch_and_push
from src.scripts.project_indexer import ProjectIndexer

PROJECT_ROOT = os.getenv("PROJECT_ROOT", ".")

# 比對 traceback 裡形如: File "src/service/discount.py", line 42, in calculate_discount
_TRACEBACK_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+)')


def locate_target_from_traceback(error_log: str, project_root: str) -> tuple[str | None, str]:
    """
    從錯誤訊息 / traceback 純文字中，定位「屬於本專案」的目標檔案路徑。

    做法：抓出所有 `File "...", line N` frame，過濾掉第三方套件路徑
    (.venv / site-packages / conda 等)，只留下落在 project_root 底下的 frame，
    取最後一個（通常最貼近實際出錯的那一行）。

    回傳: (target_file 絕對路徑, 或 None 代表定位失敗；錯誤摘要文字)
    """
    abs_root = os.path.abspath(project_root)
    frames = _TRACEBACK_FRAME_RE.findall(error_log)

    target_file = None
    for file_path, _line in frames:
        abs_path = os.path.abspath(file_path)
        is_third_party = any(
            marker in abs_path for marker in (".venv", "site-packages", "conda", "dist-packages")
        )
        if abs_path.startswith(abs_root) and not is_third_party and os.path.exists(abs_path):
            target_file = abs_path  # 保留最後一筆落在專案內的 frame

    # 錯誤摘要：抓最後一行非空白內容 (通常是 ExceptionType: message)
    lines = [line for line in error_log.strip().splitlines() if line.strip()]
    summary = lines[-1] if lines else error_log.strip()

    return target_file, summary


def fetch_3tier_context(target_file: str, indexer: ProjectIndexer) -> tuple[str, str, str]:
    """
    獲取三層上下文 context：
    - Layer 1: 全域專案 AST 骨架 (來自 IR / ModuleInfo)
    - Layer 2: 目標檔案的 Import 依賴關係 (來自 IR / ModuleInfo)
    - Layer 3: 目標檔案現有原始碼
    """
    # 1. 讀取目標檔案原始碼 (Layer 3)
    with open(target_file, "r", encoding="utf-8") as f:
        existing_code = f.read()

    # 2. 取得全域架構與模組依賴 (Layer 1 & Layer 2)，皆由 IR 動態解析而來
    target_rel_path = os.path.relpath(target_file, indexer.project_root)
    global_context = indexer.get_global_context_text(target_rel_path=target_rel_path)
    dependency_context = indexer.get_dependency_text(target_rel_path)

    return global_context, dependency_context, existing_code


def repair_file_with_prompt(target_file: str, user_prompt: str):
    """透過自然的 Prompt 輸入與三層專案 Context，自動修復指定的檔案"""
    print(f"\n🚀 開始針對 [{target_file}] 執行 Prompt 自動修復任務...")

    # 1. 檢查檔案是否存在
    if not os.path.exists(target_file):
        print(f"❌ 錯誤: 找不到目標檔案 {target_file}")
        return

    # 2. 建立全專案 IR 索引，再擷取三層 Context
    print("🔍 正在掃描整個專案以建立情境索引 (IR / AST)...")
    indexer = ProjectIndexer(PROJECT_ROOT).build()
    global_ctx, dep_ctx, existing_code = fetch_3tier_context(target_file, indexer)

    # 3. 組合三層 Context 的 Task 描述 (Prompt)
    full_task_prompt = f"""
修復目標檔案：{target_file}

【第一層：專案全域 AST 骨架 (Global Context)】:
{global_ctx}

【第二層：目標檔案模組依賴 (Dependency Context)】:
{dep_ctx}

【第三層：目標檔案現有程式碼 (Target Code)】:
```python
{existing_code}
```

【修復需求 / Issue 描述】:
{user_prompt}

【修復規範】:
1. 請參考專案全域架構與模組依賴關係，針對【目標檔案現有程式碼】進行修改或重構。
2. 修改時避免破壞其他檔案對此檔案的呼叫方式（例如不要隨意更動已被其他檔案引用的函式簽名）。
3. 請輸出完整且可執行的 Python 程式碼。
4. 必須在代碼末尾附帶 2~3 個 assert 斷言測試（或 if __name__ == '__main__': 測試區塊），確保沙盒執行時能驗證邏輯正確性。
"""

    # 4. 初始化 Agent 依賴項
    supabase_url = os.getenv("SUPABASE_URL") or "https://dummy.supabase.co"
    supabase_key = os.getenv("SUPABASE_KEY") or "dummy-key"
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    skill_library = SkillLibrary(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        gemini_api_key=gemini_api_key,
    )

    strategy = CustomSandboxVoyagerStrategy(
        skill_library=skill_library,
        llm=router,
        max_retries=3,
    )
    app = strategy.build_graph()

    initial_state = {
        "task": full_task_prompt,
        "target_file": target_file,
        "retrieved_skills": "",
        "generated_code": "",
        "execution_result": "",
        "error_log": "",
        "retry_count": 0,
        "success": False,
    }

    # 5. 執行 LangGraph 沙盒修復圖
    final_state = app.invoke(initial_state)

    # 6. 根據執行結果處理
    if final_state.get("success"):
        print("\n🎉 [沙盒測試通過] 已成功將修復單寫入 pending_reviews.json！")

        ans = input("\n👉 是否立即將修復內容覆蓋至本地檔案？(y/n): ").strip().lower()
        if ans == "y":
            apply_patch_and_push()
    else:
        print("\n❌ 修復失敗（重試達最大上限），請檢查以下報錯訊息：")
        print("--------------------------------------------------")
        print(final_state.get("error_log", "無詳細報錯"))
        print("--------------------------------------------------")


if __name__ == "__main__":
    print("=" * 50)
    print("🛠️ Voyager Prompt Code Repair CLI (3-Tier Context)")
    print("=" * 50)

    mode = input("選擇模式 (1: 手動輸入檔案路徑 / 2: 貼上錯誤訊息自動定位): ").strip()

    if mode == "2":
        print("請貼上完整錯誤訊息 / traceback，貼完後輸入一個空行結束：")
        error_lines = []
        while True:
            line = input()
            if line == "":
                break
            error_lines.append(line)
        error_log = "\n".join(error_lines)

        located_file, error_summary = locate_target_from_traceback(error_log, PROJECT_ROOT)

        if not located_file:
            print("⚠️ 無法從錯誤訊息中定位到專案內的檔案路徑，請改用模式 1 手動輸入。")
        else:
            print(f"✅ 已定位到目標檔案: {located_file}")
            print(f"   錯誤摘要: {error_summary}")
            repair_file_with_prompt(located_file, f"根據以下報錯修復此檔案：\n{error_log}")
    else:
        target = input("請輸入要修復的檔案路徑 (例如: src/service/discount.py): ").strip()
        prompt = input("請輸入修復 Prompt 需求 (例如: 當折扣小於 0 時拋出 ValueError): ").strip()

        if target and prompt:
            repair_file_with_prompt(target, prompt)
        else:
            print("⚠️ 檔案路徑與 Prompt 需求皆不可為空！")