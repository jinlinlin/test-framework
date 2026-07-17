"""
可观察接口 — 定义事件发布/订阅的统一契约（观察者模式）。

设计模式：观察者模式（Observer Pattern）
事件总线和可订阅组件实现此接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class IObservable(ABC):
    """可观察接口 — 支持事件订阅和通知的组件契约。"""

    @abstractmethod
    def subscribe(self, event_type: str, listener: Callable) -> None:
        """
        订阅指定类型的事件。

        Args:
            event_type: 事件类型标识符。
            listener: 事件回调函数。
        """

    @abstractmethod
    def unsubscribe(self, event_type: str, listener: Callable) -> None:
        """
        取消订阅指定类型的事件。

        Args:
            event_type: 事件类型标识符。
            listener: 之前注册的回调函数。
        """

    @abstractmethod
    async def notify(self, event_type: str, data: Any = None) -> None:
        """
        通知所有订阅者。

        Args:
            event_type: 触发的事件类型。
            data: 事件携带的数据。
        """
