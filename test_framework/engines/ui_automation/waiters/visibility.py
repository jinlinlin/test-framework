"""
等待可见策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import WaiterStrategy


class VisibilityWaiter(WaiterStrategy):
    """等待可见策略"""

    async def wait(self, page) -> None:
        await expect(page.locator(self._selector)).to_be_visible(**self._kwargs)

    @property
    def name(self) -> str:
        return "visibility"