# src/core/context_governance/base.py
from abc import ABC, abstractmethod
from typing import Any
from langchain_core.messages import BaseMessage, SystemMessage, trim_messages


class BaseContextCleaner(ABC):
    """上下文治理策略抽象基类"""

    @abstractmethod
    def clean(
        self,
        raw_messages: list[BaseMessage],
        system_prompt: str,
        llm: Any,
        **kwargs: Any
    ) -> list[BaseMessage]:
        """对输入的原始消息进行清洗、裁剪或重构"""
        pass