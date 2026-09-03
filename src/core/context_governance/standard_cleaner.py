from typing import Any
import tiktoken
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, trim_messages
from src.core.context_governance.base import BaseContextCleaner


# 自定义 safe token 计数器，彻底解决非 OpenAI 模型（Qwen/Groq/Gemini等）调用 trim_messages 时的 NotImplementedError 崩溃
try:
    _enc = tiktoken.get_encoding("cl100k_base")
    def _count_tokens(messages: Any) -> int:
        if isinstance(messages, str):
            return len(_enc.encode(messages))
        if isinstance(messages, BaseMessage):
            messages = [messages]
        total = 0
        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            total += 4 + len(_enc.encode(content))
        return total
except Exception:
    def _count_tokens(messages: Any) -> int:
        if isinstance(messages, str):
            return max(1, len(messages) // 2)
        if isinstance(messages, BaseMessage):
            messages = [messages]
        total = 0
        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            total += 4 + (len(content) // 2)
        return total


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

        # 2. Token 修剪 (使用自訂 count_tokens 避開模型 get_num_tokens 崩潰)
        trimmed_msgs: list[BaseMessage] = []
        if non_system_msgs:
            try:
                trimmer = trim_messages(
                    max_tokens=self.max_tokens,
                    strategy="last",
                    token_counter=_count_tokens,  # 防崩潰關鍵点
                    include_system=False,
                    allow_partial=False,
                    start_on="human",  # 保證 ToolMessage 與 tool_call 結構不被割裂
                )
                trimmed_msgs = trimmer.invoke(non_system_msgs)
            except Exception:
                # 兜底：若修剪失敗，保留最後幾條非 System 消息
                trimmed_msgs = non_system_msgs[-10:]

        # 3. 兜底保護：若修剪後完全沒有 HumanMessage，補一条 placeholder 避免 Groq/Gemini 報錯
        has_human = any(isinstance(m, HumanMessage) for m in trimmed_msgs)
        if not has_human:
            trimmed_msgs.append(HumanMessage(content="Please continue based on the above system instructions."))

        # 4. 頭部壓入唯一 SystemMessage
        return [SystemMessage(content=system_prompt)] + trimmed_msgs