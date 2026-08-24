# src/core/strategies/pipeline_strategy.py
from typing import Any, AsyncGenerator, Sequence
from langchain_core.tools import BaseTool
from src.core.pipeline_agent.agent import PipelineMultiAgentSystem
from ..strategies.base import BaseAgentStrategy

class PipelineAgentStrategy(BaseAgentStrategy):
    def __init__(self):
        self._agent_system = None

    def build(self, mcp_tools: Sequence[BaseTool]) -> None:
        self._agent_system = PipelineMultiAgentSystem(mcp_tools=mcp_tools)

    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return await self._agent_system.ainvoke(inputs, config)

    async def astream(
        self, inputs: dict[str, Any], config: dict[str, Any], stream_mode: str = "updates"
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for chunk in self._agent_system.astream(inputs, config, stream_mode=stream_mode):
            yield chunk