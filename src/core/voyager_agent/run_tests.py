"""
在提交到 GitHub 之前，先在暫存資料夾裡跑測試，確認 agent 生成的工具代碼是可用的。
用 subprocess 跑一個獨立的 pytest process（不是 import 進當前 process 裡跑），
這樣就算生成的代碼有語法錯誤或執行期例外，也不會影響到你 agent 主程式本身。

如果你想要更強的隔離（例如生成代碼本身就不可信、可能有惡意行為），
建議把這一步整個丟進 Docker container 執行，這裡先提供最小可行版本。
"""

import json
import ast
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

# 2. 寫入待審核暫存檔
def save_to_pending_store(
    item: Dict[str, Any], staging_file: str = "pending_reviews.json"
):
    """將修復單 (Patch) 寫入本地 JSON 暫存庫"""
    try:
        with open(staging_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    data.append(item)

    with open(staging_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 3. 静态 AST 安全检查函数
def check_code_safety(code: str) -> Optional[str]:
    """使用 AST 检查代码中是否存在黑名单模块或高危调用"""
    # 高危模块黑名单
    BANNED_MODULES = {"subprocess", "shutil", "socket", "urllib", "requests", "ctypes"}
    # 高危内置函数黑名单
    BANNED_FUNCTIONS = {"eval", "exec", "__import__"}

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax Error: 代碼語法錯誤 - {str(e)}"

    for node in ast.walk(tree):
        # 拦截 import xxx
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[0]
                if mod_name in BANNED_MODULES:
                    return f"Security Error: 禁止導入高危模組 '{mod_name}'。"

        # 拦截 from xxx import yyy
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_name = node.module.split(".")[0]
                if mod_name in BANNED_MODULES:
                    return f"Security Error: 禁止從高危模組 '{mod_name}' 導入內容。"

        # 拦截 eval() / exec() / __import__() 等高危函数调用
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_FUNCTIONS:
                return f"Security Error: 禁止使用高危內建函數 '{node.func.id}()'。"

    return None  # 安全校验通过

# 4. 动态 Hook Header (在沙盒内执行前注入到代码顶部)
RUNTIME_SECURITY_HEADER = """import builtins
import os

# ① 拦截 input 交互，避免沙盒 EOFError / 死锁
def dummy_input(prompt=''):
    raise ValueError('沙盒不支援 input() 交互，請將參數作為函數入參傳入。')
builtins.input = dummy_input

# ② 拦截破坏性文件系统操作
def forbidden_remove(*args, **kwargs):
    raise PermissionError('沙盒安全策略限制：禁止執行檔案或目錄刪除操作(os.remove/rmdir/unlink)。')

os.remove = forbidden_remove
os.unlink = forbidden_remove
if hasattr(os, 'rmdir'):
    os.rmdir = forbidden_remove

"""

@dataclass
class TestResult:
    passed: bool
    output: str


def run_tests(tool_code: str, test_code: str, tool_module_name: str = "tool") -> TestResult:
    """
    :param tool_code: 工具本體的原始碼
    :param test_code: 對應的測試檔原始碼（import 工具時用 `from tool import ...`）
    :param tool_module_name: 工具檔案的 module 名稱，預設 "tool"（對應 tool.py）
    """
    with tempfile.TemporaryDirectory(prefix="tool-test-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / f"{tool_module_name}.py").write_text(tool_code, encoding="utf-8")
        (tmp_path / f"test_{tool_module_name}.py").write_text(test_code, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", str(tmp_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr
        passed = result.returncode == 0

        return TestResult(passed=passed, output=output)
