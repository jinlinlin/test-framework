"""
管道执行引擎模块 — 串联阶段、过滤器和钩子的核心管道（责任链模式）。

设计模式：责任链模式（Chain of Responsibility Pattern）
Pipeline 将测试执行拆分为多个有序阶段，
支持过滤器拦截和钩子注入，实现可扩展、可插拔的执行流程。
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from .context import PipelineContext
from .filter import Filter
from .hooks import HookManager
from .stage import Stage

logger = logging.getLogger(__name__)


class Pipeline:
    """
    管道 — 串联多个阶段的责任链执行引擎。

    执行流程：
    1. 遍历已注册的阶段列表（按优先级排序）
    2. 对每个阶段，依次检查所有过滤器
    3. 过滤器全部通过 → 触发 before_stage 钩子 → 执行阶段 → 触发 after_stage 钩子
    4. 阶段执行出错 → 触发 on_error 钩子 → 调用阶段 on_error 方法
    5. 全部阶段执行完成 → 触发 on_complete 钩子

    支持链式调用：
        pipeline = Pipeline().add_stage(stage1).add_stage(stage2).add_filter(filter1)
        result = await pipeline.execute(context)
    """

    def __init__(self) -> None:
        """初始化空管道。"""
        # [(priority, Stage), ...]
        self._stages: List[Tuple[int, Stage]] = []
        self._filters: List[Filter] = []
        self._hook_manager = HookManager()

    def add_stage(self, stage: Stage, priority: int = 0) -> Pipeline:
        """
        添加执行阶段。

        Args:
            stage: 阶段实例。
            priority: 优先级（数值越小越先执行）。

        Returns:
            self（支持链式调用）。
        """
        self._stages.append((priority, stage))
        # 按优先级升序排序
        self._stages.sort(key=lambda x: x[0])
        logger.debug(f"添加管道阶段: {stage.name!r} (priority={priority})")
        return self

    def add_filter(self, filter_: Filter) -> Pipeline:
        """
        添加过滤器。

        Args:
            filter_: 过滤器实例。

        Returns:
            self（支持链式调用）。
        """
        self._filters.append(filter_)
        return self

    def on(self, event: str, callback, priority: int = 0) -> Pipeline:
        """
        注册钩子。

        Args:
            event: 钩子事件名称（before_stage/after_stage/on_error/on_complete）。
            callback: 钩子回调函数。
            priority: 优先级。

        Returns:
            self（支持链式调用）。
        """
        self._hook_manager.register(event, callback, priority)
        return self

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        执行管道 — 按优先级依次执行所有阶段。

        Args:
            context: 初始管道上下文。

        Returns:
            执行完毕后的管道上下文（包含各阶段数据和可能的错误）。
        """
        logger.info(f"管道开始执行，共 {len(self._stages)} 个阶段")

        for priority, stage in self._stages:
            # 检查是否已中止
            if context.is_aborted:
                logger.warning(f"管道已中止，跳过阶段: {stage.name!r}")
                break

            # 检查过滤器
            should_run = all(
                f.should_execute(context, stage) for f in self._filters
            )
            if not should_run:
                logger.debug(f"阶段 {stage.name!r} 被过滤器跳过")
                continue

            context.current_stage = stage.name

            try:
                # 触发 before_stage 钩子
                await self._hook_manager.trigger("before_stage", context, stage=stage)

                # 执行阶段
                context = await stage.process(context)

                # 触发 after_stage 钩子
                await self._hook_manager.trigger("after_stage", context, stage=stage)

            except Exception as e:
                # 触发 on_error 钩子
                await self._hook_manager.trigger("on_error", context, stage=stage, error=e)
                # 调用阶段错误处理
                context = await stage.on_error(context, e)

        # 触发 on_complete 钩子
        await self._hook_manager.trigger("on_complete", context)

        logger.info(
            f"管道执行完成，错误数: {len(context.errors)}，"
            f"是否中止: {context.is_aborted}"
        )
        return context

    @property
    def stage_count(self) -> int:
        """获取已注册的阶段数量。"""
        return len(self._stages)

    @property
    def hook_manager(self) -> HookManager:
        """获取钩子管理器（用于外部注册钩子）。"""
        return self._hook_manager
