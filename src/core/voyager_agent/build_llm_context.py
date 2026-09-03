"""
Voyager Code Repair Toolset
專為 Voyager Agent 設計的程式碼修復工具箱（包含 AST 結構分析、檔案 I/O、測試執行）。
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import tool

# 匯入專案自訂的 Parser 與 Bridge 工具
from src.ingestion.bridge.llm_context_builder import build_llm_context
from src.ingestion.parser.factory import ParserFactory


# ==========================================
# 1. AST 與專案探索工具 (AST & Exploration)
# ==========================================

@tool
def get_project_symbol_index(
    project_dir: str = ".",
    exclude_dirs: Optional[List[str]] = None
) -> str:
    """
    【層級 1：專案全域符號索引】
    掃描指定專案目錄下的所有原始碼檔案（如 .py, .tsx, .ts, .jsx, .js），
    運用 Parser 提取每個檔案的類別 (Class) 與函式 (Function) 簽名，生成全域輕量化索引。
    
    用途：當不確定 Bug 在哪個檔案，或需要尋找特定 Function/Component 位於何處時使用。
    """
    if exclude_dirs is None:
        exclude_dirs = [
            "node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", "artifacts"
        ]

    target_path = Path(project_dir)
    if not target_path.exists():
        return f"錯誤：找不到專案目錄 '{project_dir}'"

    symbol_index = []
    supported_extensions = {".py", ".tsx", ".ts", ".jsx", ".js"}

    try:
        for root, dirs, files in os.walk(target_path):
            # 過濾不需要掃描的目錄
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in supported_extensions:
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            source = f.read()

                        filename = file_path.name
                        parser = ParserFactory.get_by_filename(filename)
                        module = parser.parse(source, filename=filename)

                        # 提煉輕量化階層資訊
                        classes = [cls.name for cls in module.classes]
                        functions = [func.name for func in module.functions]
                        
                        # 若是 React 元件（如果有解析到 components 或 ui_fields）
                        components = getattr(module, "components", [])

                        symbols_str = []
                        if classes:
                            symbols_str.append(f"Classes: [{', '.join(classes)}]")
                        if functions:
                            symbols_str.append(f"Functions: [{', '.join(functions)}]")
                        if components:
                            symbols_str.append(f"Components: [{', '.join([c.name for c in components])}]")

                        rel_path = file_path.as_posix()
                        if symbols_str:
                            symbol_index.append(f"- {rel_path} -> {' | '.join(symbols_str)}")
                        else:
                            symbol_index.append(f"- {rel_path} -> (無顯式類別/函式宣告)")

                    except Exception as parse_err:
                        # 當某些檔案語法特殊解析失敗時，回退降級處理
                        symbol_index.append(f"- {file_path.as_posix()} -> (AST 解析跳過: {parse_err})")

        if not symbol_index:
            return "未在專案目錄中找到支援的原始碼檔案。"

        return "【專案全域符號索引】:\n" + "\n".join(symbol_index)

    except Exception as e:
        return f"生成全域符號索引時發生錯誤: {str(e)}"


@tool
def get_code_ast_summary(source_path: str) -> str:
    """
    【層級 2：單檔 AST 結構摘要】
    傳入特定程式碼檔案路徑，解析其 AST 並回傳結構化摘要（包含 Class/Function 簽名、控制流、UI 綁定與業務提示等）。
    
    用途：當已知目標檔案路徑，需要精準了解檔案內部結構骨架與控制邏輯時使用，比閱讀 Raw Code 更節省 Token。
    """
    path = Path(source_path)
    if not path.exists():
        return f"錯誤：找不到檔案 '{source_path}'"

    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()

        filename = path.name
        parser = ParserFactory.get_by_filename(filename)
        module = parser.parse(source, filename=filename)

        # 利用 build_llm_context 生成高度濃縮且具業務語意的 Context
        ast_context = build_llm_context(module)
        return ast_context
    except Exception as e:
        return f"AST 解析失敗: {str(e)}"


# ==========================================
# 2. 檔案 I/O 工具 (File Operations)
# ==========================================

@tool
def read_source_code(source_path: str) -> str:
    """
    【層級 3：單檔 Raw Code 讀取】
    讀取指定原始碼檔案的全文內容。
    
    用途：當已經定位出 Bug 具體所在的 Function 或位置，需要閱讀完整原始碼以進行修正時使用。
    """
    path = Path(source_path)
    if not path.exists():
        return f"錯誤：找不到檔案 '{source_path}'"

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"讀取檔案失敗 '{source_path}': {str(e)}"


@tool
def write_source_code(source_path: str, new_content: str) -> str:
    """
    【程式碼覆寫工具】
    將修復後的完整程式碼覆寫回指定檔案。
    
    用途：當 Voyager 完成程式碼修復邏輯後，呼叫此工具套用變更。
    """
    path = Path(source_path)
    try:
        # 自動建立不存在的父目錄
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"成功更新檔案: {source_path}"
    except Exception as e:
        return f"寫入檔案失敗 '{source_path}': {str(e)}"


# ==========================================
# 3. 測試與驗證工具 (Verification & Test)
# ==========================================

@tool
def run_linter_or_test(command: str) -> str:
    """
    【測試與 Linter 執行工具】
    在系統 Shell 中執行測試或 Linter 指令（例如 'pytest tests/test_login.py'、'npm test' 或 'flake8'）。
    
    用途：讓 Voyager 在修正程式碼後執行測試，獲取 STDOUT / STDERR 以驗證修復是否成功或進行 Self-Correction。
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60  # 設定 60 秒 Timeout 避免測試卡死
        )
        output = []
        if result.stdout:
            output.append(f"=== STDOUT ===\n{result.stdout}")
        if result.stderr:
            output.append(f"=== STDERR ===\n{result.stderr}")
        
        status = "成功 (Exit Code 0)" if result.returncode == 0 else f"失敗 (Exit Code {result.returncode})"
        output_str = "\n".join(output) if output else "(無輸出內容)"
        
        return f"執行結果: {status}\n\n{output_str}"
    except subprocess.TimeoutExpired:
        return f"執行指令失敗: 指令 '{command}' 執行超過 60 秒超時。"
    except Exception as e:
        return f"執行指令時發生例外錯誤: {str(e)}"


# ==========================================
# 4. 導出的 Tool 集合（方便一次性註冊給 Voyager）
# ==========================================

VOYAGER_CODE_REPAIR_TOOLS = [
    get_project_symbol_index,
    get_code_ast_summary,
    read_source_code,
    write_source_code,
    run_linter_or_test,
]