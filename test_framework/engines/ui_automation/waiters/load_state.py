"""
等待加载状态策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from .base import WaiterStrategy


class LoadStateWaiter(WaiterStrategy):
    """等待加载状态策略"""

    def __init__(self, selector: str = "", state: str = "networkidle", **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._state = state

    async def wait(self, page) -> None:
        await page.wait_for_load_state(self._state, **self._kwargs)

    @property
    def name(self) -> str:
        return "load_state"