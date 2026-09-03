from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.ingestion.ir.model import ModuleInfo
from src.ingestion.parser.factory import ParserFactory

# Parser 本身透過各語言模組的 @ParserFactory.register 自行完成註冊，
# 這裡只要確保對應的 parser 模組有被 import 過一次即可（例如在專案的
# src/ingestion/parser/__init__.py 裡 import 所有語言 parser）。
# 若還沒有集中的 __init__，先手動 import 一次 PythonParser 觸發註冊：
from src.ingestion.parser.python_parser import PythonParser  # noqa: F401


class ProjectIndexer:
    """基於既有 IR (ModuleInfo) 建立三層情境索引：

    1. Global Context   - 全專案的 class / function 簽名 (含型別資訊，來自 IR)
    2. Dependency Graph - 檔案間的 import 關係
    3. File Content     - 不在此類別內，由呼叫端另外讀取目標檔案原始碼
    """

    def __init__(self, project_root: str, extensions: tuple[str, ...] | None = None):
        self.project_root = Path(project_root).resolve()
        # 不指定的話，掃描 ParserFactory 目前註冊過的所有副檔名
        self.extensions = extensions
        self.modules: Dict[str, ModuleInfo] = {}  # {relative_path: ModuleInfo}

    def build(self) -> "ProjectIndexer":
        skip_dirs = {".venv", "venv", "node_modules", "__pycache__", ".git"}
        allowed_exts = set(self.extensions) if self.extensions else None

        for file_path in self.project_root.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in skip_dirs for part in file_path.parts):
                continue
            if allowed_exts is not None and file_path.suffix not in allowed_exts:
                continue

            rel_path = str(file_path.relative_to(self.project_root))

            try:
                parser = ParserFactory.get_by_filename(file_path.name)
            except ValueError:
                # 副檔名沒有對應的 parser（例如 .md, .json），略過不索引
                continue

            try:
                source = file_path.read_text(encoding="utf-8")
                module_info = parser.parse(source, filename=rel_path)
            except (SyntaxError, UnicodeDecodeError) as e:
                print(f"⚠️ 略過解析失敗的檔案: {rel_path} ({e})")
                continue

            self.modules[rel_path] = module_info

        return self

    # ------------------------------------------------
    # Layer 1: Global Context
    # ------------------------------------------------

    def get_global_context_text(
        self,
        target_rel_path: Optional[str] = None,
        max_files: int = 50,
    ) -> str:
        """輸出全域簽名摘要。

        若提供 target_rel_path，只列出與該檔案有直接依賴關係的檔案
        （它 import 的、以及 import 它的），而不是整個專案，避免 prompt 塞爆、
        也讓 LLM 只看到真正相關的上下文。沒有給 target_rel_path 時退回列出前
        max_files 個檔案。
        """
        if target_rel_path is not None:
            relevant_paths = self._related_files(target_rel_path)
            items = [(p, self.modules[p]) for p in relevant_paths if p in self.modules]
        else:
            items = list(self.modules.items())[:max_files]

        lines: List[str] = []
        for rel_path, module in items:
            file_lines: List[str] = []

            for clazz in module.classes:
                bases = f"({', '.join(clazz.bases)})" if clazz.bases else ""
                file_lines.append(f"  class {clazz.name}{bases}")
                for method in clazz.methods:
                    file_lines.append(f"    - {self._format_signature(method)}")

            for func in module.functions:
                file_lines.append(f"  {self._format_signature(func)}")

            if file_lines:
                lines.append(f"### {rel_path}")
                lines.extend(file_lines)

        return "\n".join(lines) if lines else "（沒有找到相關的簽名資訊）"

    @staticmethod
    def _format_signature(method) -> str:
        params = ", ".join(
            f"{p.name}: {p.type}" if getattr(p, "type", None) else p.name
            for p in method.parameters
        )
        ret = f" -> {method.return_type}" if getattr(method, "return_type", None) else ""
        return f"def {method.name}({params}){ret}"

    # ------------------------------------------------
    # Layer 2: Dependency Graph
    # ------------------------------------------------

    def _module_to_dotted(self, rel_path: str) -> str:
        return rel_path[: -len(Path(rel_path).suffix)].replace(os.sep, ".")

    def _related_files(self, target_rel_path: str) -> Set[str]:
        """回傳與 target_rel_path 有直接 import 關係的檔案集合（雙向）。"""
        related: Set[str] = set()
        target_module = self.modules.get(target_rel_path)
        target_dotted = self._module_to_dotted(target_rel_path)

        # target 自己 import 了誰 -> 嘗試比對成專案內的相對路徑
        if target_module:
            for imp in target_module.imports:
                for rel_path in self.modules:
                    dotted = self._module_to_dotted(rel_path)
                    if dotted in imp.name or imp.name in dotted:
                        related.add(rel_path)

        # 誰 import 了 target
        for rel_path, module in self.modules.items():
            if rel_path == target_rel_path:
                continue
            if any(target_dotted in imp.name or imp.name in target_dotted for imp in module.imports):
                related.add(rel_path)

        return related

    def get_dependency_text(self, target_rel_path: str) -> str:
        """回傳與目標檔案直接相關的依賴關係：它 import 了誰、誰 import 了它"""
        target_module = self.modules.get(target_rel_path)
        lines: List[str] = []

        if target_module and target_module.imports:
            lines.append(f"[{target_rel_path}] 匯入的模組:")
            lines.extend(f"  - {imp.name}" for imp in target_module.imports)

        target_dotted = self._module_to_dotted(target_rel_path)
        callers = [
            rel for rel, module in self.modules.items()
            if rel != target_rel_path
            and any(target_dotted in imp.name or imp.name in target_dotted for imp in module.imports)
        ]
        if callers:
            lines.append(f"\n匯入 [{target_rel_path}] 的檔案 (需注意相容性):")
            lines.extend(f"  - {c}" for c in callers)

        return "\n".join(lines) if lines else "（無法解析到直接依賴關係，可能是動態 import 或外部套件）"