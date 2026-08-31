# tests/test_orchestrator_unit.py
'''
2. 單元測試：Mock 外部服務，驗證 Agent 的重試 (Self-Correction) 邏輯
這裡我們 Mock 掉 Gemini、Supabase 和 GitHub，只驗證 「當第一次測試失敗時，Agent 會不會自動拿著 Error Log 去做第二次重試」：
'''
import pytest
from unittest.mock import MagicMock, patch
from src.core.voyager_agent.orchestrator import VoyagerAgentOrchestrator

@patch("src.core.voyager_agent.orchestrator.get_file_content")
@patch("src.core.voyager_agent.orchestrator.submit_code_change")
@patch("src.core.voyager_agent.orchestrator.SkillLibrary")
@patch("src.core.voyager_agent.orchestrator.genai.Client")
def test_agent_self_correction_loop(
    mock_genai_client, 
    mock_skill_lib, 
    mock_submit_code, 
    mock_get_file
):
    # 1. 模擬 GitHub 打開現有檔案
    mock_get_file.return_value = "def old_func(): pass"

    # 2. 模擬 SkillLibrary (避免 json.dumps 拿到 MagicMock 導致 TypeError)
    mock_skill_instance = MagicMock()
    mock_skill_lib.return_value = mock_skill_instance
    mock_skill_instance.retrieve_skills.return_value = []

    # 3. 模擬 GitHub PR 提交回應
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/test-owner/test-repo/pull/1"
    mock_pr.number = 1
    mock_submit_code.return_value = mock_pr

    # 4. 模擬 Gemini 回應 (第 1 次給錯代碼，第 2 次給對代碼)
    mock_ai_instance = MagicMock()
    mock_genai_client.return_value = mock_ai_instance

    response_1 = MagicMock()
    response_1.text = '{"skill_name": "fix_bug", "description": "fix", "tool_code": "def fix(): return 1/0", "test_code": "from tool import fix\\ndef test_fix(): fix()"}'
    
    response_2 = MagicMock()
    response_2.text = '{"skill_name": "fix_bug", "description": "fix", "tool_code": "def fix(): return 1", "test_code": "from tool import fix\\ndef test_fix(): assert fix() == 1"}'
    
    # 讓 API 第一次回傳 bad_code，第二次回傳 good_code
    mock_ai_instance.models.generate_content.side_effect = [response_1, response_2]

    # 5. 初始化 Orchestrator
    orchestrator = VoyagerAgentOrchestrator(
        owner="test-owner",
        repo="test-repo",
        supabase_url="http://fake-url",
        supabase_key="fake-key",
        gemini_api_key="fake-key"
    )

    # 6. 執行任務
    res = orchestrator.fix_bug_or_add_feature(
        task_description="修復 Bug",
        target_file_path="src/dummy.py",
        max_retries=3
    )

    # 7. 斷言 (Assert)
    assert res["status"] == "success"
    # 驗證 generate_content 是否真的被呼叫了 2 次（代表有觸發 Self-Correction）
    assert mock_ai_instance.models.generate_content.call_count == 2