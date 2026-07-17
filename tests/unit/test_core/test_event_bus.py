# -*- coding: utf-8 -*-
"""EventBus 单元测试。

测试事件发布、订阅、监听器注册与触发。
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock


class TestEventBus:
    """测试事件总线核心功能。"""

    def test_subscribe_and_publish(self):
        """测试订阅事件后发布能正确触发回调。"""
        from test_framework.core.events.event_bus import EventBus

        bus = EventBus()
        bus._listeners.clear()

        callback = MagicMock()
        bus.subscribe("test.event", callback)

        # 发布事件
        bus.publish("test.event", {"data": "hello"})

        # 验证回调被调用
        callback.assert_called_once()

    def test_unsubscribe(self):
        """测试取消订阅后不再触发回调。"""
        from test_framework.core.events.event_bus import EventBus

        bus = EventBus()
        bus._listeners.clear()

        callback = MagicMock()
        bus.subscribe("test.event", callback)
        bus.unsubscribe("test.event", callback)

        bus.publish("test.event", {"data": "hello"})
        callback.assert_not_called()

    def test_multiple_listeners(self):
        """测试同一事件多个监听器都能被触发。"""
        from test_framework.core.events.event_bus import EventBus

        bus = EventBus()
        bus._listeners.clear()

        cb1 = MagicMock()
        cb2 = MagicMock()
        bus.subscribe("multi.event", cb1)
        bus.subscribe("multi.event", cb2)

        bus.publish("multi.event", {})

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_publish_no_listeners(self):
        """测试发布无人监听的事件不报错。"""
        from test_framework.core.events.event_bus import EventBus

        bus = EventBus()
        bus._listeners.clear()

        # 不应抛出异常
        bus.publish("nobody.listens", {"data": 123})
