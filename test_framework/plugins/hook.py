"""
插件钩子系统 — 允许插件在框架关键节点注入逻辑。

钩子类型：
- before_engine_run: 引擎执行前
- after_engine_run: 引擎执行后
- before_report: 报告生成前
- after_report: 报告生成后
- on_error: 发生错误时
- on_test_completed: 单个测试完成时
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 钩子回调类型
HookCallback = Callable[..., Coroutine[Any, Any, None]]


class PluginHookSystem:
    """
    插件钩子系统。

    允许插件在框架关键生命周期节点注册回调函数。
    同一钩子可注册多个回调，按优先级排序执行。

    使用示例::

        hooks = PluginHookSystem()
        hooks.register_hook("before_engine_run", my_callback, priority=10)
        await hooks.trigger("before_engine_run", engine=engine, config=config)
    """

    def __init__(self) -> None:
        """初始化钩子系统。"""
        # hook_name -> [(priority, callback), ...]
        self._hooks: Dict[str, List[Tuple[int, HookCallback]]] = {}

    def register_hook(
        self,
        hook_name: str,
        callback: HookCallback,
        priority: int = 0,
    ) -> None:
        """
        注册钩子回调。

        Args:
            hook_name: 钩子名称。
            callback: 异步回调函数。
            priority: 优先级（数值越大越先执行）。
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append((priority, callback))
        # 按优先级降序排序
        self._hooks[hook_name].sort(key=lambda x: x[0], reverse=True)
        logger.debug(f"注册钩子: {hook_name} -> {callback.__name__} (priority={priority})")

    def unregister_hook(self, hook_name: str, callback: HookCallback) -> None:
        """注销钩子回调。"""
        if hook_name in self._hooks:
            self._hooks[hook_name] = [
                (p, cb) for p, cb in self._hooks[hook_name] if cb != callback
            ]

    async def trigger(self, hook_name: str, **kwargs: Any) -> None:
        """
        触发钩子，按优先级顺序执行所有回调。

        Args:
            hook_name: 钩子名称。
            **kwargs: 传递给回调的参数。
        """
        callbacks = self._hooks.get(hook_name, [])
        for priority, callback in callbacks:
            try:
                await callback(**kwargs)
            except Exception as e:
                logger.error(f"钩子 {hook_name}/{callback.__name__} 执行失败: {e}")

    def list_hooks(self) -> Dict[str, List[str]]:
        """列出所有已注册的钩子及其回调。"""
        result: Dict[str, List[str]] = {}
        for hook_name, callbacks in self._hooks.items():
            result[hook_name] = [cb.__name__ for _, cb in callbacks]
        return result

    def has_hook(self, hook_name: str) -> bool:
        """检查是否有注册的钩子。"""
        return hook_name in self._hooks and len(self._hooks[hook_name]) > 0
