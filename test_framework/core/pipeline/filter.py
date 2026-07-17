"""
过滤器模块 — 控制管道阶段是否执行（过滤器模式）。

Filter 可在管道执行前判断某个 Stage 是否应该运行，
实现条件执行、环境过滤等能力。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .context import PipelineContext
from .stage import Stage


class Filter(ABC):
    """
    管道过滤器抽象基类。

    在 Pipeline.execute() 中，每个 Stage 执行前都会经过所有 Filter 判断。
    任一 Filter 返回 False 则跳过该 Stage。
    """

    @abstractmethod
    def should_execute(self, context: PipelineContext, stage: Stage) -> bool:
        """
        判断阶段是否应该执行。

        Args:
            context: 当前管道上下文。
            stage: 待判断的阶段实例。

        Returns:
            返回 True 表示执行，False 表示跳过。
        """


class TagFilter(Filter):
    """
    标签过滤器 — 根据上下文标签决定是否执行。

    仅当 context.metadata 中包含指定标签时才执行阶段。
    """

    def __init__(self, required_tag: str) -> None:
        self._required_tag = required_tag

    def should_execute(self, context: PipelineContext, stage: Stage) -> bool:
        return self._required_tag in context.metadata.get("tags", [])
