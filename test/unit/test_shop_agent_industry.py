"""
Test that the shop agent system prompt dynamically includes industry information.
"""

from core.shop_agent.prompts import SHOP_SYSTEM_PROMPT


def test_industry_in_prompt():
    """Test that the industry field is properly included in the system prompt."""
    
    # Test data with different industries
    test_cases = [
        {
            "industry": "手机",
            "expected_in_prompt": "你是一个专业且严谨的{industry}店 AI 助手。"
        },
        {
            "industry": "电脑",
            "expected_in_prompt": "你是一个专业且严谨的{industry}店 AI 助手。"
        },
        {
            "industry": "数码配件",
            "expected_in_prompt": "你是一个专业且严谨的{industry}店 AI 助手。"
        }
    ]
    
    for test_case in test_cases:
        industry = test_case["industry"]
        expected_text = test_case["expected_in_prompt"]
        
        # Format the prompt with test data
        formatted_prompt = SHOP_SYSTEM_PROMPT.format(
            user_id="123",
            user_name="测试用户",
            role="店员",
            store_name="测试店铺",
            industry=industry
        )
        
        # Verify the industry appears in the prompt
        assert expected_text in formatted_prompt, f"Expected '{expected_text}' not found in prompt for industry '{industry}'"
        print(f"✓ Industry '{industry}' correctly included in prompt")
    
    print("\nAll tests passed!")


def test_industry_in_capabilities():
    """Test that the capabilities description includes industry-specific language."""
    
    # Test with phone industry
    phone_prompt = SHOP_SYSTEM_PROMPT.format(
        user_id="123",
        user_name="测试用户",
        role="店员",
        store_name="手机店",
        industry="手机"
    )
    
    assert "我可以为您提供手机收机入库" in phone_prompt, "Phone industry should appear in capabilities"
    print("✓ Phone industry correctly appears in capabilities description")
    
    # Test with computer industry
    computer_prompt = SHOP_SYSTEM_PROMPT.format(
        user_id="456",
        user_name="另一个用户",
        role="经理",
        store_name="电脑店",
        industry="电脑"
    )
    
    assert "我可以为您提供电脑收机入库" in computer_prompt, "Computer industry should appear in capabilities"
    print("✓ Computer industry correctly appears in capabilities description")


if __name__ == "__main__":
    test_industry_in_prompt()
    test_industry_in_capabilities()
