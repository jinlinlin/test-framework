"""
等待启用策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import WaiterStrategy


class EnabledWaiter(WaiterStrategy):
    """等待启用策略"""

    async def wait(self, page) -> None:
        await expect(page.locator(self._selector)).to_be_enabled(**self._kwargs)

    @property
    def name(self) -> str:
        return "enabled"