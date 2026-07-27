from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from src.ingestion.ir.model import ModuleInfo


class BaseParser(ABC):
    """所有語言 Parser 的基類。

    每個語言的實作（PythonParser、JavaParser...）都應該繼承這個類別，
    並設定 `language` / `extensions`，再透過 ParserFactory.register 註冊，
    讓上層可以用語言名稱或副檔名動態取得對應的 Parser。
    """

    #: 此 Parser 支援的語言識別碼，例如 "python"、"java"
    language: ClassVar[str] = ""

    #: 此 Parser 支援的副檔名列表，例如 [".py"]
    extensions: ClassVar[list[str]] = []

    @abstractmethod
    def parse(self, source: str, filename: str | None = None) -> ModuleInfo:
        """將原始碼字串解析為語言無關的 IR（ModuleInfo）。

        Args:
            source: 原始碼內容。
            filename: 選填，來源檔案名稱，會寫入 ModuleInfo.filename。
        """
        ...
