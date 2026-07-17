"""
等待导航策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from .base import WaiterStrategy


class NavigationWaiter(WaiterStrategy):
    """等待导航策略"""

    async def wait(self, page) -> None:
        async with page.expect_navigation(**self._kwargs):
            pass

    @property
    def name(self) -> str:
        return "navigation"