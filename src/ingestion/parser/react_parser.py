from __future__ import annotations

import warnings
from typing import ClassVar

from tree_sitter_languages import get_parser

from src.ingestion.ir.model import ModuleInfo
from src.ingestion.parser.base import BaseParser
from src.ingestion.parser.factory import ParserFactory
from src.ingestion.parser.react_visitor import ReactVisitor

# tree-sitter-languages 目前釋出的版本仍呼叫舊版 tree-sitter 的 Language(path, name)
# 建構子，會跳出 FutureWarning，這裡先過濾掉避免污染 log。等 tree-sitter-languages
# 更新相容新版 API 之後可以移除這行。
warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")

# tsx 語法是 jsx 的超集（多了型別標註），兩種副檔名都用同一個 grammar 解析即可。
_TREE_SITTER_LANGUAGE = "tsx"


@ParserFactory.register
class ReactParser(BaseParser):
    """React (JSX/TSX) 原始碼 → IR (ModuleInfo)

    只做結構層級的解析：import、function/class component、props、hook 呼叫。
    不解析元件內部完整的陳述式（if/for/return...），這點和 PythonParser 不同。
    """

    language = "react"
    extensions: ClassVar[list[str]] = [".jsx", ".tsx"]

    def __init__(self):
        # tree-sitter 的 parser 物件不是 thread-safe 共用的最佳實踐，
        # 所以每個 ReactParser instance 自己拿一份（ParserFactory 本來就是每次 get_by_* 都 new 一個）。
        self._ts_parser = get_parser(_TREE_SITTER_LANGUAGE)

    def parse(self, source: str, filename: str | None = None) -> ModuleInfo:
        source_bytes = source.encode("utf-8")

        tree = self._ts_parser.parse(source_bytes)

        visitor = ReactVisitor(source_bytes)

        module = visitor.visit(tree.root_node)

        module.filename = filename

        return module
