from typing import Any
from langchain_core.messages import BaseMessage, SystemMessage, trim_messages
from src.core.context_governance.base import BaseContextCleaner


class StandardSlidingCleaner(BaseContextCleaner):
    """通用單 Agent 清洗器：滑動窗口 + System去重 + Tool Call 配對保護"""

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    def clean(
        self,
        raw_messages: list[BaseMessage],
        system_prompt: str,
        llm: Any,
        **kwargs: Any
    ) -> list[BaseMessage]:
        # 1. 剝離歷史中的 SystemMessage
        non_system_msgs = [m for m in raw_messages if not isinstance(m, SystemMessage)]

        # 2. 獲取 Token 計算對象（如果 llm 有 get_model 則取底層 ChatModel，否則直接使用 llm）
        token_counter_target = llm.get_model() if hasattr(llm, "get_model") else llm

        # 3. Token 修剪
        trimmer = trim_messages(
            max_tokens=self.max_tokens,
            strategy="last",
            token_counter=token_counter_target,
            include_system=False,
            allow_partial=False,
            start_on="human",  # 保證 ToolMessage 與 tool_call 結構不被割裂
        )
        trimmed_msgs = trimmer.invoke(non_system_msgs)

        # 4. 頭部壓入唯一 SystemMessage
        return [SystemMessage(content=system_prompt)] + trimmed_msgs