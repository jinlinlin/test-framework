"""
core.events 包 — 事件驱动系统（观察者模式）。

提供全局事件总线、事件对象、事件类型定义和监听器注册机制。
"""
from .event import Event
from .event_bus import EventBus
from .event_types import EventTypes
from .listeners import ListenerRegistry, listener

__all__ = [
    "Event",
    "EventBus",
    "EventTypes",
    "ListenerRegistry",
    "listener",
]
