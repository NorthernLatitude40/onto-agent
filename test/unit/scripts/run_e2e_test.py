# scripts/run_e2e_test.py
import os
from dotenv import load_dotenv
# 先載入 .env 環境變數
load_dotenv()

# 1. 導入 Orchestrator 與你的同步函數
from src.scripts.sync_skills_from_db import SKILLS_DIR, sync_skills
from src.github.orchestrator import VoyagerAgentOrchestrator

def run_real_e2e_test():
  print("🚀 開始執行真實端到端 (E2E) 整合測試...")

  # Step 1: 初始化 Orchestrator
  orchestrator = VoyagerAgentOrchestrator(
      owner=os.getenv("GITHUB_REPO_OWNER"),
      repo="practice",  # 專門測試用的 Sandbox Repo
      supabase_url=os.getenv("SUPABASE_URL"),
      supabase_key=os.getenv("SUPABASE_KEY"),
      gemini_api_key=os.getenv("GEMINI_API_KEY"),
      base_branch="main",
  )

  # Step 2: 執行 Agent 任務 (生成代碼 -> 本地沙盒測試 -> 存入 Supabase DB -> 提交 GitHub PR)
  print("\n🤖 [Phase 1] 觸發 Agent 進行技能生成與沙盒驗證...")
  result = orchestrator.fix_bug_or_add_feature(
      task_description="編寫一個判斷字串是否為回文 (Palindrome) 的工具函數",
      max_retries=2,
  )

  print(f"\n✅ Agent 執行完成！技能名稱: {result['skill_name']}")

  # Step 3: 觸發排程同步腳本 (從 Supabase 拉取並寫入本地 .py 檔)
  print("\n🔄 [Phase 2] 觸發排程腳本同步 Supabase 技能到本地...")
  sync_skills()

  # Step 4: E2E 驗證本地檔案是否確實產出
  expected_file = os.path.join(SKILLS_DIR, f"{result['skill_name']}.py")
  assert os.path.exists(expected_file), (
      f"❌ E2E 測試失敗: 本地未找到同步檔案 {expected_file}"
  )

  print("\n🎉 全流程 E2E 測試成功閉環！")
  print(f"  ├─ 本地技能檔案: {expected_file}")
  print(f"  └─ GitHub PR 網址: {result.get('pr_url')}")


if __name__ == "__main__":
  run_real_e2e_test()