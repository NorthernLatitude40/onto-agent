"""
在提交到 GitHub 之前，先在暫存資料夾裡跑測試，確認 agent 生成的工具代碼是可用的。
用 subprocess 跑一個獨立的 pytest process（不是 import 進當前 process 裡跑），
這樣就算生成的代碼有語法錯誤或執行期例外，也不會影響到你 agent 主程式本身。

如果你想要更強的隔離（例如生成代碼本身就不可信、可能有惡意行為），
建議把這一步整個丟進 Docker container 執行，這裡先提供最小可行版本。
"""

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


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
