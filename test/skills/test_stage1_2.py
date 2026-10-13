import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from src.core.llm_router import router
from src.core.voyager_agent.skill_library import SkillLibrary
from core.voyager_agent.skill_generation_strategy import CustomSandboxVoyagerStrategy


def test_agent_and_staging():
    print("==================================================")
    print("🚀 [測試 1/2] 開始執行 Agent 沙盒修復與 Patch 生成...")
    print("==================================================")

    # 1. 修正路徑為沒有 s 的 service
    target_file = "src/service/discount.py"

    if not os.path.exists(target_file):
        print(f"❌ 錯誤: 找不到 {target_file}，請確認檔案是否有建立在 src/service/ 下！")
        return

    with open(target_file, "r", encoding="utf-8") as f:
        existing_code = f.read()

    # 2. 初始化資源與 Agent
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

    # 3. Prompt 中的目標檔案也統一改為 src/service/discount.py
    issue_desc = (
        f"修復目標檔案：{target_file}\n\n"
        f"【現有程式碼】:\n```python\n{existing_code}\n```\n\n"
        "【修復需求】:\n"
        "請修復 calculate_discount 函數：\n"
        "1. 修正計算邏輯：打折後價格應為 price * (1 - discount_rate)。\n"
        "2. 邊界檢查：若 discount_rate 不在 0 到 1 之間（例如 < 0 或 > 1），必須拋出 ValueError('折扣率必須介於 0 與 1 之間')。\n\n"
        "【測試驗證要求】:\n"
        "請在生成的程式碼末尾附帶以下驗證區塊，確保沙盒執行時能驗證修復結果：\n"
        "```python\n"
        "assert calculate_discount(100, 0.2) == 80\n"
        "try:\n"
        "    calculate_discount(100, 1.5)\n"
        "    assert False, '未成功拋出 ValueError'\n"
        "except ValueError as e:\n"
        "    assert str(e) == '折扣率必須介於 0 與 1 之間'\n\n"
        "print('✅ 沙盒驗證：所有單元測試通過！')\n"
        "```\n"
    )

    initial_state = {
        "task": issue_desc,
        "target_file": target_file,
        "retrieved_skills": "",
        "generated_code": "",
        "execution_result": "",
        "error_log": "",
        "retry_count": 0,
        "success": False,
    }

    print(f"📌 修復目標檔案: {target_file}")
    final_state = app.invoke(initial_state)

    print("\n--------------------------------------------------")
    if final_state.get("success"):
        print("✅ 沙盒修復並驗證成功！")
        print("\n【沙盒執行輸出】:")
        print(final_state.get("execution_result"))
        print("\n【產出的修復程式碼】:")
        print(final_state.get("generated_code"))
    else:
        print("❌ 執行失敗，報錯訊息：")
        print(final_state.get("error_log"))

    # 4. 檢查暫存檔 pending_reviews.json
    print("\n==================================================")
    print("🔍 [測試 2/2] 檢查修復暫存檔 (pending_reviews.json)...")
    print("==================================================")

    staging_file = "pending_reviews.json"
    if os.path.exists(staging_file):
        with open(staging_file, "r", encoding="utf-8") as f:
            reviews = json.load(f)

        latest = reviews[-1]

        print("【最新寫入的修復單內容】:")
        print(f" - Review ID         : {latest.get('review_id')}")
        print(f" - 目標檔案 (Target) : {latest.get('target_file')}")
        print(f" - 審核狀態 (Status) : {latest.get('status')}")
        print("--------------------------------------------------")
        print(f" - 修復後代碼 (fixed_code) :\n{latest.get('fixed_code')}")
        print("--------------------------------------------------")

        if (
            latest.get("status") == "PENDING_REVIEW"
            and latest.get("target_file") == target_file
            and latest.get("fixed_code")
        ):
            print("\n🎉 驗證成功！修復單已成功包含 fixed_code 與 target_file。")
        else:
            print("\n⚠️ 暫存單欄位內容不完整，請檢查物件內容。")


if __name__ == "__main__":
    test_agent_and_staging()