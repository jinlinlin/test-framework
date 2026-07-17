"""
监听器注册模块 — 自动发现和注册事件监听器。

支持通过装饰器 @listener 标记函数为事件监听器，
ListenerRegistry 可扫描包路径自动注册。
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from .event import Event

# 全局监听器装饰器标记
_LISTENER_ATTR = "_event_listener"


def listener(event_type: str, priority: int = 0) -> Callable:
    """
    事件监听器装饰器 — 标记函数为特定事件的监听器。

    Args:
        event_type: 监听的事件类型（如 'test_case.completed'）。
        priority: 优先级，数值越小越先执行，默认 0。

    Returns:
        装饰后的函数（附加 _event_listener 属性）。

    Example:
        @listener(EventTypes.TEST_CASE_COMPLETED)
        async def on_case_completed(event: Event) -> None:
            print(f"用例 {event.data['case_id']} 完成")
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, _LISTENER_ATTR, {
            "event_type": event_type,
            "priority": priority,
        })
        return func
    return decorator


class ListenerRegistry:
    """
    监听器注册表 — 管理事件监听器的注册和自动发现。

    支持两种注册方式：
    1. 手动注册：register(event_type, handler)
    2. 自动发现：auto_discover(package_path) 扫描包下所有 @listener 标记的函数
    """

    def __init__(self) -> None:
        """初始化空的监听器注册表。"""
        # event_type -> [(priority, handler), ...]
        self._handlers: Dict[str, List[tuple]] = defaultdict(list)

    def register(self, event_type: str, handler: Callable, priority: int = 0) -> None:
        """
        手动注册事件监听器。

        Args:
            event_type: 事件类型。
            handler: 事件处理函数（支持同步和异步）。
            priority: 优先级（数值越小越先执行）。
        """
        self._handlers[event_type].append((priority, handler))
        # 按优先级排序
        self._handlers[event_type].sort(key=lambda x: x[0])

    def unregister(self, event_type: str, handler: Callable) -> None:
        """
        移除事件监听器。

        Args:
            event_type: 事件类型。
            handler: 要移除的处理函数。
        """
        self._handlers[event_type] = [
            (p, h) for p, h in self._handlers[event_type] if h is not handler
        ]

    def get_handlers(self, event_type: str) -> List[Callable]:
        """
        获取指定事件类型的所有监听器（按优先级排序）。

        Args:
            event_type: 事件类型。

        Returns:
            处理函数列表。
        """
        return [handler for _, handler in self._handlers.get(event_type, [])]

    def auto_discover(self, package_path: str) -> int:
        """
        自动扫描包路径，发现并注册所有 @listener 标记的函数。

        Args:
            package_path: Python 包路径（如 'test_framework.listeners'）。

        Returns:
            自动注册的监听器数量。
        """
        count = 0
        try:
            package = importlib.import_module(package_path)
        except ImportError:
            return 0

        # 遍历包下所有模块
        for _, module_name, _ in pkgutil.walk_packages(
            package.__path__, prefix=package.__name__ + "."
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            # 扫描模块中的所有对象
            for _, obj in inspect.getmembers(module):
                if callable(obj) and hasattr(obj, _LISTENER_ATTR):
                    info = getattr(obj, _LISTENER_ATTR)
                    self.register(
                        event_type=info["event_type"],
                        handler=obj,
                        priority=info.get("priority", 0),
                    )
                    count += 1

        return count
