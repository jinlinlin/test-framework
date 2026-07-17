"""
事件总线模块 — 全局事件发布/订阅中心（单例模式）。

设计模式：单例模式 + 观察者模式
EventBus 是框架事件驱动架构的核心组件，
所有引擎、报告器、插件通过事件总线进行松耦合通信。
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from .event import Event

logger = logging.getLogger(__name__)


class EventBus:
    """
    事件总线（单例模式）。

    全局唯一的事件发布/订阅中心，管理所有事件的监听器注册和事件分发。
    支持同步和异步监听器，支持优先级排序。

    Attributes:
        _instance: 单例实例引用。
        _subscribers: 事件类型 → 监听器列表的映射。

    Example:
        bus = EventBus()
        bus.subscribe("test.completed", my_handler)
        await bus.publish(Event("test.completed", data={...}))
    """

    _instance: Optional[EventBus] = None

    def __new__(cls) -> EventBus:
        """确保全局只有一个 EventBus 实例（单例模式）。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = defaultdict(list)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化事件总线（仅首次生效）。"""
        if self._initialized:
            return
        self._initialized = True
        self._subscribers: Dict[str, List[Tuple[int, Callable]]] = defaultdict(list)

    def subscribe(self, event_type: str, listener: Callable, priority: int = 0) -> None:
        """
        订阅指定事件类型。

        Args:
            event_type: 事件类型标识符（如 'test_case.completed'）。
            listener: 事件处理函数（同步或异步均可）。
            priority: 优先级，数值越小越先执行，默认 0。
        """
        self._subscribers[event_type].append((priority, listener))
        # 按优先级升序排序（小的先执行）
        self._subscribers[event_type].sort(key=lambda x: x[0])
        logger.debug(f"订阅事件 {event_type!r}，监听器: {listener.__name__}，优先级: {priority}")

    def unsubscribe(self, event_type: str, listener: Callable) -> None:
        """
        取消订阅指定事件类型。

        Args:
            event_type: 事件类型标识符。
            listener: 之前注册的处理函数。
        """
        self._subscribers[event_type] = [
            (p, h) for p, h in self._subscribers[event_type] if h is not listener
        ]
        logger.debug(f"取消订阅事件 {event_type!r}，监听器: {listener.__name__}")

    async def publish(self, event: Event) -> None:
        """
        异步发布事件 — 依次调用所有匹配的监听器。

        支持异步和同步监听器：
        - 异步监听器：直接 await
        - 同步监听器：在线程中执行（避免阻塞事件循环）

        Args:
            event: 要发布的事件对象。
        """
        handlers = self._subscribers.get(event.type, [])
        for priority, handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    # 同步函数放到线程池执行，避免阻塞
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, handler, event)
            except Exception as e:
                # 单个监听器异常不影响其他监听器执行
                logger.error(f"事件监听器 {handler.__name__} 处理 {event.type!r} 时出错: {e}")

    def publish_sync(self, event: Event) -> None:
        """
        同步发布事件 — 在当前线程中依次调用所有监听器。

        适用于非异步上下文（如 __init__ 或同步工具函数中）。

        Args:
            event: 要发布的事件对象。
        """
        handlers = self._subscribers.get(event.type, [])
        for priority, handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    # 在同步上下文中运行协程
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(handler(event))
                    finally:
                        loop.close()
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"事件监听器 {handler.__name__} 处理 {event.type!r} 时出错: {e}")

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """
        获取订阅者数量。

        Args:
            event_type: 指定事件类型，为 None 时返回全部订阅者总数。

        Returns:
            订阅者数量。
        """
        if event_type:
            return len(self._subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self._subscribers.values())

    def reset(self) -> None:
        """
        重置事件总线 — 清除所有订阅者。

        仅在测试环境中使用，用于隔离测试用例之间的事件状态。
        """
        self._subscribers.clear()
        logger.debug("事件总线已重置")

    @classmethod
    def reset_instance(cls) -> None:
        """
        重置单例实例 — 用于测试环境完全重建事件总线。

        警告：生产环境不应调用此方法。
        """
        cls._instance = None
