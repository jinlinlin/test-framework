"""
管道阶段模块 — 定义管道中可执行的处理阶段（责任链模式）。

每个 Stage 代表管道中的一个处理步骤，
子类实现 process() 方法完成具体逻辑。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from .context import PipelineContext

logger = logging.getLogger(__name__)


class Stage(ABC):
    """
    管道阶段抽象基类。

    所有管道阶段必须继承此类并实现 process() 方法。
    可选实现 on_error() 自定义错误处理逻辑。

    Attributes:
        name: 阶段名称，用于日志和调试。
    """

    name: str = "unnamed_stage"

    @abstractmethod
    async def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理管道上下文。

        Args:
            context: 当前管道上下文。

        Returns:
            处理后的管道上下文（可修改并返回同一对象）。
        """

    async def on_error(self, context: PipelineContext, error: Exception) -> PipelineContext:
        """
        错误处理钩子 — 当 process() 抛出异常时调用。

        默认行为：记录错误并添加到 context.errors。
        子类可覆盖此方法实现自定义错误恢复逻辑。

        Args:
            context: 当前管道上下文。
            error: 捕获到的异常。

        Returns:
            处理后的管道上下文。
        """
        logger.error(f"阶段 {self.name!r} 执行出错: {error}")
        context.add_error(error)
        return context
