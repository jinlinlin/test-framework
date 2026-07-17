"""
事件基类模块 — 定义事件对象的标准数据结构。

所有通过 EventBus 发布的事件均使用 Event 类或其子类。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class Event:
    """
    事件基类 — 事件总线中传递的标准事件对象。

    Attributes:
        type: 事件类型标识符（如 'test_case.completed'）。
        source: 事件源对象（产生事件的组件）。
        data: 事件携带的数据字典。
        timestamp: 事件创建时间。
    """

    type: str
    source: Any = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        """返回事件的可读字符串表示。"""
        return f"Event(type={self.type!r}, source={type(self.source).__name__}, ts={self.timestamp.isoformat()})"
