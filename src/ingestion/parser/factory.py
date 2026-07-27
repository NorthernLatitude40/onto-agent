from __future__ import annotations

import os
from typing import ClassVar, TypeVar

from src.ingestion.parser.base import BaseParser

T = TypeVar("T", bound=type[BaseParser])


class ParserFactory:
    """多語言 Parser 的註冊與查找中心。

    用法：
        @ParserFactory.register
        class PythonParser(BaseParser):
            language = "python"
            extensions = [".py"]
            ...

        parser = ParserFactory.get_by_language("python")
        parser = ParserFactory.get_by_filename("app.py")
    """

    _by_language: ClassVar[dict[str, type[BaseParser]]] = {}
    _by_extension: ClassVar[dict[str, type[BaseParser]]] = {}

    @classmethod
    def register(cls, parser_cls: T) -> T:
        if not parser_cls.language:
            raise ValueError(f"{parser_cls.__name__} 必須設定 language 屬性")

        cls._by_language[parser_cls.language] = parser_cls

        for ext in parser_cls.extensions:
            cls._by_extension[ext] = parser_cls

        return parser_cls

    @classmethod
    def get_by_language(cls, language: str) -> BaseParser:
        try:
            parser_cls = cls._by_language[language]
        except KeyError as exc:
            supported = list(cls._by_language)
            raise ValueError(f"未註冊的語言: {language!r}，目前支援: {supported}") from exc
        return parser_cls()

    @classmethod
    def get_by_filename(cls, filename: str) -> BaseParser:
        _, ext = os.path.splitext(filename)
        try:
            parser_cls = cls._by_extension[ext]
        except KeyError as exc:
            supported = list(cls._by_extension)
            raise ValueError(f"未支援的副檔名: {ext!r}，目前支援: {supported}") from exc
        return parser_cls()

    @classmethod
    def supported_languages(cls) -> list[str]:
        return list(cls._by_language)
