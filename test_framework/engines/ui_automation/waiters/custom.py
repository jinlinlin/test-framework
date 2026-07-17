"""
自定义等待策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from typing import Callable

from .base import WaiterStrategy


class CustomWaiter(WaiterStrategy):
    """自定义等待策略"""

    def __init__(self, selector: str = "", condition: Callable = None, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._condition = condition

    async def wait(self, page) -> None:
        if self._condition:
            await page.wait_for_function(self._condition, **self._kwargs)
        else:
            await page.wait_for_timeout(1000)

    @property
    def name(self) -> str:
        return "custom"