# src/core/context_governance/pipeline_cleaner.py (设计预留)
from typing import Any, AsyncGenerator, Sequence
from langchain_core.messages import BaseMessage
from src.core.context_governance import BaseContextCleaner

class PipelineStageCleaner(BaseContextCleaner):
    """Pipeline 阶段隔离清洗器：只保留上游节点产出的核心 Artifact/JSON，抛弃中间思考和 Tool Calls"""

    def clean(
        self,
        raw_messages: list[BaseMessage],
        system_prompt: str,
        llm: Any,
        **kwargs: Any
    ) -> list[BaseMessage]:
        # 未来 Pipeline 逻辑：
        # 1. 遍历消息提取特定 Stage 的最终结果（如 Artifact）
        # 2. 丢弃上阶段所有 ToolMessage / intermediate steps
        # 3. 重新组装极简的 Prompt 传给下一个节点
        pass