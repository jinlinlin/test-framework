"""
复合等待策略。

设计模式：策略模式（Strategy）+ 组合模式（Composite）
"""
from __future__ import annotations

from typing import List

from .base import WaiterStrategy


class CompositeWaiter(WaiterStrategy):
    """复合等待策略"""

    def __init__(self, waiters: List[WaiterStrategy], **kwargs) -> None:
        super().__init__("", **kwargs)
        self._waiters = waiters

    async def wait(self, page) -> None:
        for waiter in self._waiters:
            await waiter.wait(page)

    @property
    def name(self) -> str:
        return "composite"