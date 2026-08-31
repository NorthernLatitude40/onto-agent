"""
「修 bug / 改既有代碼」的完整流程範例。

跟 example/run.py（新增工具）的差異只有一步：
  多了 get_file_content() 這個「先讀現有代碼」的步驟。
其餘（跑測試 -> 通過才提交）完全共用同一套邏輯，submit_code_change 會自動
判斷 path 對應的檔案已存在，走 update 而不是 create。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv

from github.run_tests import run_tests
from github.submit_tool import get_file_content, submit_code_change, FileChange

load_dotenv()

OWNER = os.environ["GITHUB_REPO_OWNER"]
REPO = os.environ["GITHUB_REPO_NAME"]
BASE_BRANCH = os.environ.get("GITHUB_BASE_BRANCH", "main")

# 要修的檔案在 repo 裡的路徑（換成你實際要修的檔案）
TARGET_PATH = "tools/weather_lookup.py"


def generate_fix(current_code: str, bug_description: str) -> str:
    """
    這裡是你接 LLM 的地方 —— 把現有代碼 + bug 描述丟給你的 agent，
    請它回傳「修改後的完整檔案內容」。這個範例先用假邏輯示範接口長什麼樣，
    實際請換成呼叫你自己的 LLM / agent。
    """
    # TODO: 換成真正的 LLM 呼叫，例如：
    # return your_llm_client.fix_code(current_code=current_code, bug=bug_description)
    return current_code.replace(
        'raise ValueError(f"no data for {city}")',
        'raise ValueError(f"no weather data available for city: {city}")',
    )


def main() -> None:
    bug_description = "錯誤訊息不夠清楚，應該說明是天氣資料查不到"

    print(f"[1/4] 讀取現有代碼: {TARGET_PATH} ...")
    current_code = get_file_content(OWNER, REPO, TARGET_PATH, ref=BASE_BRANCH)

    print("[2/4] 生成修復（這裡接你的 LLM）...")
    fixed_code = generate_fix(current_code, bug_description)

    if fixed_code == current_code:
        print("生成結果跟原始代碼一樣，沒有變更，中止。")
        return

    print("[3/4] 跑測試 ...")
    # 測試檔如果 repo 裡已經有現成的，也可以用 get_file_content 讀出來一起帶進去；
    # 這裡先沿用固定的測試內容示範。
    test_code = '''
import pytest
from tool import weather_lookup


def test_returns_weather_for_known_city():
    assert weather_lookup("Taipei") == "28C, sunny"


def test_raises_for_unknown_city():
    with pytest.raises(ValueError):
        weather_lookup("Nowhere")
'''.strip()

    result = run_tests(fixed_code, test_code)
    if not result.passed:
        print("測試未通過，取消提交：\n", result.output)
        sys.exit(1)
    print("測試通過 ✅")

    print("[4/4] 提交修復（開分支 + commit 更新 + PR）...")
    pr = submit_code_change(
        owner=OWNER,
        repo=REPO,
        base_branch=BASE_BRANCH,
        change_id="fix-weather-lookup-error-message",
        files=[
            FileChange(
                path=TARGET_PATH,
                content=fixed_code,
                commit_message=f"fix: {bug_description}",
            ),
        ],
        pr_title="[Agent] 修復: weather_lookup 錯誤訊息不清楚",
        pr_body=(
            "此 PR 由 agent 自動產生。\n\n"
            f"- 問題描述: {bug_description}\n"
            "- 本地測試狀態: ✅ 通過\n\n"
            "請 review 後再合併（此流程不會自動 merge）。"
        ),
    )

    print("完成 🎉")
    print("PR 已建立:", pr.html_url)


if __name__ == "__main__":
    main()
