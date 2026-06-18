import json
import os
import sys
import yaml  # 💡 記得確保你的環境有安裝 pyyaml (pip install pyyaml)

# =================================================================
# 🌟 雙重路徑保險：確保 Python 無論如何都能在 src/ 底下找到 core
# =================================================================
current_workspace = os.getcwd()  # C:\Users\ww\langgraph_workspace
src_path = os.path.join(current_workspace, "src")

if current_workspace not in sys.path:
    sys.path.append(current_workspace)
if src_path not in sys.path:
    sys.path.append(src_path)

from core.harness import AgentHarness


def execute_harness_test(test_suite: str) -> str:
    """
    讀取指定的 YAML 測試集，由 AgentHarness 執行測試，並返回 Markdown 格式報告
    """
    # 1. 定義設定檔路徑與輸出路徑
    config_path = f"test/test_harness/configs/{test_suite}.yaml"
    output_path = f"test/test_harness/results/{test_suite}_result.json"

    if not os.path.exists(config_path):
        return f"❌ 找不到指定的測試集設定檔: {config_path}"

    # 確保輸出目錄存在
    os.makedirs("test/test_harness/results", exist_ok=True)

    # 2. 讀取 YAML 測試案例
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
    except Exception as e:
        return f"🚨 讀取 YAML 設定檔失敗: {str(e)}"

    # 假設 YAML 結構中包含一個 test_cases 列表，如果沒有則給個預設空列表
    test_cases = config_data.get("test_cases", [])
    if not test_cases:
        return f"⚠️ 警告: 設定檔 {config_path} 中沒有找到任何測試案例 (test_cases)。"

    # 3. 初始化並啟動 AgentHarness 引擎
    try:
        print("🚀 正在初始化 AgentHarness 引擎...")
        harness = AgentHarness()
        harness.bootstrap()
        print("✨ AgentHarness 引擎啟動成功，開始執行測試案例...\n")

        total_cases = len(test_cases)
        passed_cases = 0
        failures = []

        # 4. 逐一執行測試案例
        for idx, case in enumerate(test_cases, 1):
            user_input = case.get("input", "")
            expected_output = case.get("expected", "")

            print(f"🏃 [{idx}/{total_cases}] 正在測試 Case: {user_input}")

            # 使用獨立的 thread_id 確保每次測試對話乾淨，或者維持同一個模擬流程
            thread_id = f"test_{test_suite}_{idx}"

            # 呼叫大腦獲取真實回應
            actual_output = harness.interact(
                user_message=user_input, thread_id=thread_id
            )

            # 驗證邏輯：這裡使用簡單的包含性校驗（可依據你們專案的斷言邏輯修改）
            # 如果 AI 回傳的文字包含了預期關鍵字，或預期結果為空字串，算通過
            if expected_output in actual_output:
                passed_cases += 1
            else:
                failures.append(
                    {
                        "input": user_input,
                        "expected": expected_output,
                        "actual": actual_output,
                        "reason": "AI 實際回應與預期結果不符",
                    }
                )

        # 5. 計算統計數據並產出 JSON 報告
        success_rate = (
            round((passed_cases / total_cases) * 100, 2) if total_cases > 0 else 0
        )

        result_data = {
            "total_cases": total_cases,
            "success_rate": success_rate,
            "avg_latency_seconds": 0.0,  # 預留欄位，若有需要可加計時器
            "failures": failures,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 測試完成！完整 JSON 報告已寫入: {output_path}")

        # 6. 建立給 LLM / 人類閱讀的 Markdown 摘要
        summary = f"### 📊 Agent Harness 測試報告: {test_suite}\n"
        summary += f"- **總測試案例數**: {total_cases}\n"
        summary += f"- **成功率**: {success_rate}%\n\n"

        summary += "#### ❌ 失敗案例詳情:\n"
        if not failures:
            summary += "🎉 所有測試案例全部通過！\n"
        else:
            for fail in failures:
                summary += f"- **Case**: {fail.get('input')}\n"
                summary += f"  - *預期結果*: {fail.get('expected')}\n"
                summary += f"  - *實際結果*: {fail.get('actual')}\n"
                summary += f"  - *錯誤原因*: {fail.get('reason')}\n"

        return summary

    except Exception as e:
        import traceback

        return f"🚨 運行測試時發生未知錯誤: {str(e)}\n{traceback.format_exc()}"


if __name__ == "__main__":
    # 執行你指定的 wechat_pay_flow 測試集
    report = execute_harness_test("wechat_pay_flow")

    print("\n================ 最終測試報告 (Markdown) ================\n")
    print(report)
    print("========================================================")
