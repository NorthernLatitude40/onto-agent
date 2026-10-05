# tests/test_sandbox.py
'''
1. 測試 run_tests 沙盒隔離（不用打任何外部 API）
驗證你的 subprocess 是不是真的能捕捉到 pytest 成功与失敗。
'''
from src.core.voyager_agent.run_tests import run_tests

def test_run_tests_success():
    """測試：當語法與測試都正確時，應返回 passed=True"""
    tool_code = "def add(a, b):\n    return a + b\n"
    test_code = "from tool import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    
    result = run_tests(tool_code, test_code)
    assert result.passed is True
    assert "1 passed" in result.output

def test_run_tests_failure_correction():
    """測試：當工具邏輯寫錯時，應返回 passed=False，並帶有 traceback"""
    tool_code = "def add(a, b):\n    return a - b\n"  # 故意寫錯
    test_code = "from tool import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    
    result = run_tests(tool_code, test_code)
    assert result.passed is False
    assert "AssertionError" in result.output