import ast
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

# ================================
# 1. AST 安全检查模块
# ================================

# 高危模块黑名单
BANNED_MODULES = {"subprocess", "shutil", "socket", "urllib", "requests", "ctypes"}
# 高危内置函数黑名单
BANNED_FUNCTIONS = {"eval", "exec", "__import__"}


def check_code_safety(code: str) -> Optional[str]:
    """
    使用 AST 检查代码中是否存在黑名单模块或高危调用
    :return: 若存在安全隐患返回错误信息，通过则返回 None
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax Error: 代码语法错误 - {str(e)}"

    for node in ast.walk(tree):
        # 拦截 import xxx
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[0]
                if mod_name in BANNED_MODULES:
                    return f"Security Error: 禁止导入高危模块 '{mod_name}'。"

        # 拦截 from xxx import yyy
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_name = node.module.split(".")[0]
                if mod_name in BANNED_MODULES:
                    return f"Security Error: 禁止从高危模块 '{mod_name}' 导入内容。"

        # 拦截 eval() / exec() / __import__() 等高危函数调用
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_FUNCTIONS:
                return f"Security Error: 禁止使用高危内置函数 '{node.func.id}()'。"

    return None


# ================================
# 2. 测试结果与沙盒执行模块
# ================================

@dataclass
class TestResult:
    passed: bool
    output: str


def run_tests_with_ast_check(
    tool_code: str,
    test_code: str,
    tool_module_name: str = "tool",
    timeout: int = 30
) -> TestResult:
    """
    在暂存文件夹里跑 pytest 测试，并在执行前经过 AST 安全校验。
    
    :param tool_code: 工具本体的源代码
    :param test_code: 对应的测试文件源代码（import 工具时用 `from tool import ...`）
    :param tool_module_name: 工具文件的 module 名称，默认 "tool"
    :param timeout: 超时限制（秒）
    """
    # 💡 步骤 1: 对工具代码与测试代码先做 AST 静态安全拦截
    tool_safety_err = check_code_safety(tool_code)
    if tool_safety_err:
        return TestResult(passed=False, output=f"AST Security Intercept (Tool):\n{tool_safety_err}")

    test_safety_err = check_code_safety(test_code)
    if test_safety_err:
        return TestResult(passed=False, output=f"AST Security Intercept (Test):\n{test_safety_err}")

    # 💡 步骤 2: 放入隔离的临时目录，调用子进程执行 pytest
    with tempfile.TemporaryDirectory(prefix="tool-test-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / f"{tool_module_name}.py").write_text(tool_code, encoding="utf-8")
        (tmp_path / f"test_{tool_module_name}.py").write_text(test_code, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-v", str(tmp_path)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout + result.stderr
            passed = result.returncode == 0
            return TestResult(passed=passed, output=output)

        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                output=f"Execution Error: Pytest 执行超时 ({timeout} 秒)，可能存在死循环。"
            )
        except Exception as e:
            return TestResult(
                passed=False,
                output=f"Execution Exception: 执行期间触发未捕捉异常 - {str(e)}"
            )