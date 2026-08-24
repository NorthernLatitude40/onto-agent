# src/core/strategies/factory.py
from typing import Type
from .base import BaseAgentStrategy
from ..pipeline_agent.pipeline_strategy import PipelineAgentStrategy
from ..shop_agent.shop_strategy import ShopAgentStrategy  

class AgentStrategyFactory:
    _registry: dict[str, Type[BaseAgentStrategy]] = {
        "pipeline": PipelineAgentStrategy,
        "shop": ShopAgentStrategy,
    }

    @classmethod
    def create(cls, strategy_type: str, **kwargs) -> BaseAgentStrategy:
        strategy_cls = cls._registry.get(strategy_type.lower())
        if not strategy_cls:
            raise ValueError(f"未知的 Agent 策略类型: {strategy_type}。可用策略: {list(cls._registry.keys())}")
        return strategy_cls(**kwargs)

    @classmethod
    def register(cls, name: str, strategy_cls: Type[BaseAgentStrategy]):
        """支持运行时动态扩展注册新的 Strategy"""
        cls._registry[name.lower()] = strategy_cls