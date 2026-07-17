"""
钩子系统模块 — 管道阶段前后的生命周期钩子。

支持四类钩子：
    - before_stage: 阶段执行前触发
    - after_stage: 阶段执行后触发
    - on_error: 阶段执行出错时触发
    - on_complete: 整个管道执行完成时触发
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List

from .context import PipelineContext

logger = logging.getLogger(__name__)

# 支持的钩子事件类型
HOOK_EVENTS = ("before_stage", "after_stage", "on_error", "on_complete")


class HookManager:
    """
    钩子管理器 — 管理管道生命周期钩子的注册和触发。

    钩子按优先级排序（数值越小越先执行），
    单个钩子异常不影响其他钩子执行。
    """

    def __init__(self) -> None:
        """初始化空的钩子管理器。"""
        # event_name → [(priority, callback), ...]
        self._hooks: Dict[str, List[tuple]] = defaultdict(list)

    def register(self, event: str, callback: Callable, priority: int = 0) -> None:
        """
        注册钩子。

        Args:
            event: 钩子事件名称（before_stage/after_stage/on_error/on_complete）。
            callback: 钩子回调函数，签名为 async def hook(context, **kwargs)。
            priority: 优先级（数值越小越先执行）。

        Raises:
            ValueError: 当事件名称不在支持列表中时抛出。
        """
        if event not in HOOK_EVENTS:
            raise ValueError(f"不支持的钩子事件: {event!r}，可选: {HOOK_EVENTS}")

        self._hooks[event].append((priority, callback))
        self._hooks[event].sort(key=lambda x: x[0])
        logger.debug(f"注册钩子: {event!r} → {callback.__name__} (priority={priority})")

    def unregister(self, event: str, callback: Callable) -> None:
        """移除指定钩子。"""
        self._hooks[event] = [
            (p, cb) for p, cb in self._hooks[event] if cb is not callback
        ]

    async def trigger(self, event: str, context: PipelineContext, **kwargs: Any) -> None:
        """
        触发指定事件的所有钩子。

        Args:
            event: 钩子事件名称。
            context: 管道上下文。
            **kwargs: 附加参数（如 stage 实例）。
        """
        for priority, callback in self._hooks.get(event, []):
            try:
                await callback(context, **kwargs)
            except Exception as e:
                logger.error(f"钩子 {callback.__name__}({event}) 执行出错: {e}")

    def list_hooks(self) -> Dict[str, List[str]]:
        """列出所有已注册钩子的名称。"""
        return {
            event: [cb.__name__ for _, cb in hooks]
            for event, hooks in self._hooks.items()
        }
