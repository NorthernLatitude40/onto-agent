"""
完整流程範例：
  1. （假設）agent 已生成新工具的代碼 + 對應測試
  2. 在沙箱裡跑測試
  3. 通過才提交到 GitHub（開分支 + commit + PR）
  4. 沒通過就中止，不碰 GitHub

實際使用時，把 tool_code / test_code 換成你 agent 真正生成的內容即可，
前面接的 LLM 生成邏輯不在這個範例裡（那是你 tool-creation 那一層的事）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import os

from github.run_tests import run_tests
from github.submit_tool import submit_new_tool, FileChange

load_dotenv()

TOOL_NAME = "weather_lookup"

TOOL_CODE = '''
def weather_lookup(city: str) -> str:
    fake_data = {"taipei": "28C, sunny", "osaka": "26C, cloudy"}
    key = city.lower()
    if key not in fake_data:
        raise ValueError(f"no data for {city}")
    return fake_data[key]
'''.strip()

TEST_CODE = '''
import pytest
from tool import weather_lookup


def test_returns_weather_for_known_city():
    assert weather_lookup("Taipei") == "28C, sunny"


def test_raises_for_unknown_city():
    with pytest.raises(ValueError):
        weather_lookup("Nowhere")
'''.strip()


def main() -> None:
    print(f"[1/3] 跑測試: {TOOL_NAME} ...")
    result = run_tests(TOOL_CODE, TEST_CODE)

    if not result.passed:
        print("測試未通過，取消提交：\n", result.output)
        sys.exit(1)
    print("測試通過 ✅")

    print("[2/3] 提交到 GitHub（開分支 + commit + PR）...")
    pr = submit_new_tool(
        owner=os.environ["GITHUB_REPO_OWNER"],
        repo=os.environ["GITHUB_REPO_NAME"],
        base_branch=os.environ.get("GITHUB_BASE_BRANCH", "main"),
        tool_name=TOOL_NAME,
        files=[
            FileChange(
                path=f"tools/{TOOL_NAME}.py",
                content=TOOL_CODE,
                commit_message=f"feat: 新增工具 {TOOL_NAME}",
            ),
            FileChange(
                path=f"tools/tests/test_{TOOL_NAME}.py",
                content=TEST_CODE,
                commit_message=f"test: 新增 {TOOL_NAME} 測試",
            ),
        ],
        pr_title=f"[Agent] 新增工具: {TOOL_NAME}",
        pr_body=(
            "此 PR 由 agent 自動產生。\n\n"
            f"- 工具名稱: `{TOOL_NAME}`\n"
            "- 本地測試狀態: ✅ 通過\n\n"
            "請 review 後再合併（此流程不會自動 merge）。"
        ),
    )

    print("[3/3] 完成 🎉")
    print("PR 已建立:", pr.html_url)


if __name__ == "__main__":
    main()
