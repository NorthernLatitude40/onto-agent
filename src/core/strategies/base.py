# src/core/strategies/base.py
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Sequence
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

# 导入上下文清洗组件
from src.core.context_governance.standard_cleaner import StandardSlidingCleaner, BaseContextCleaner


class BaseAgentStrategy(ABC):
    """Agent 策略抽象基类"""

    def __init__(self, context_cleaner: BaseContextCleaner | None = None):
        # 💡 默认注入标准滑动窗口清洗器，但允许外部/子类替换为自定义 Cleaner（如 PipelineCleaner）
        self.context_cleaner = context_cleaner or StandardSlidingCleaner(max_tokens=4000)

    def prepare_input_messages(
        self,
        raw_messages: list[BaseMessage],
        system_prompt: str,
        llm: Any,
        cleaner_override: BaseContextCleaner | None = None,
        **kwargs: Any
    ) -> list[BaseMessage]:
        """
        统一上下文准备入口：
        支持使用策略默认的 context_cleaner，或者节点特异化的 cleaner_override
        """
        cleaner = cleaner_override or self.context_cleaner
        return cleaner.clean(
            raw_messages=raw_messages,
            system_prompt=system_prompt,
            llm=llm,
            **kwargs
        )

    @abstractmethod
    def build(self, mcp_tools: Sequence[BaseTool]) -> None:
        pass

    @abstractmethod
    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def astream(
        self, inputs: dict[str, Any], config: dict[str, Any], stream_mode: str = "updates"
    ) -> AsyncGenerator[dict[str, Any], None]:
        pass