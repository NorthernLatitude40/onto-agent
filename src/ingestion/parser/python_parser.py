from __future__ import annotations

import ast
from typing import Optional

from src.ingestion.ir.model import ModuleInfo
from src.ingestion.parser.base import BaseParser
from src.ingestion.parser.factory import ParserFactory
from src.ingestion.parser.python_visitor import PythonVisitor


@ParserFactory.register
class PythonParser(BaseParser):
    """Python 原始碼 → IR (ModuleInfo)"""

    language = "python"
    extensions = [".py"]

    def parse(self, source: str, filename: Optional[str] = None) -> ModuleInfo:

        tree = ast.parse(source)

        visitor = PythonVisitor()

        visitor.visit(tree)

        visitor.module.filename = filename

        return visitor.module
