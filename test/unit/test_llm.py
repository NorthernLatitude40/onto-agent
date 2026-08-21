import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage
from src.core.llm_router import router, LLMRouter


def test_llm_router_status():
    """测试 Router 状态获取功能"""
    status = router.status
    print("\n当前 Router 节点可用状态:", status)
    
    assert "gemini" in status
    assert "openrouter" in status
    assert "siliconflow" in status
    assert "huggingface" in status


def test_llm_router_live_invoke():
    """
    真实网络请求测试：测试当前可用节点能否正常回复
    注：请确保 .env / config 中配置了有效的 API KEY
    """
    router.reset()  # 确保重置所有状态
    messages = [HumanMessage(content="回复两个字：收到")]
    
    try:
        response = router.invoke(messages)
        print(f"\n[真实测试成功] 返回内容: {response.content}")
        assert response.content is not None
        assert len(str(response.content)) > 0
    except RuntimeError as e:
        pytest.fail(f"所有模型调用均失败，错误信息: {e}")


def test_llm_router_fallback_chain(monkeypatch):
    """
    降级逻辑 Mock 测试：模拟 Gemini 和 OpenRouter 陆续报错，
    验证请求是否能自动降级并流转到 Siliconflow。
    """
    # 实例化一个新的 Router 进行隔离测试
    test_router = LLMRouter()

    # 1. Mock 失败的底层组件
    mock_failing_llm = MagicMock()
    mock_failing_llm.invoke.side_effect = Exception("模拟 API 额度不足 (402) 或网络超时")

    # 2. Mock 成功的底层组件 (Siliconflow)
    mock_successful_llm = MagicMock()
    mock_successful_response = MagicMock()
    mock_successful_response.content = "Siliconflow 处理成功"
    mock_successful_llm.invoke.return_value = mock_successful_response

    # 将故障模拟注入到 Level 1 和 Level 2
    test_router.gemini = mock_failing_llm
    test_router.openrouter = mock_failing_llm
    test_router.siliconflow = mock_successful_llm

    messages = [HumanMessage(content="测试降级机制")]

    # 执行调用
    response = test_router.invoke(messages)

    # 验证降级断言
    assert test_router.gemini_available is False, "Gemini 在失败后状态应标记为不可用"
    assert test_router.openrouter_available is False, "OpenRouter 在失败后状态应标记为不可用"
    assert test_router.siliconflow_available is True, "Siliconflow 应保持可用状态"
    assert response.content == "Siliconflow 处理成功"

    # 测试 reset 功能
    test_router.reset()
    assert test_router.gemini_available is True
    assert test_router.openrouter_available is True
    assert test_router.siliconflow_available is True


if __name__ == "__main__":
    # 直接运行该文件进行快速手动测试
    print("=== 开始运行单元测试 ===")
    test_llm_router_status()
    print("\n=== 运行 Mock 降级测试 ===")
    test_llm_router_fallback_chain(None)
    print("\n=== 运行真实调用测试 ===")
    test_llm_router_live_invoke()
    print("\n🎉 所有测试通过！")