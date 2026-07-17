"""
等待存在策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import WaiterStrategy


class PresenceWaiter(WaiterStrategy):
    """等待存在策略"""

    async def wait(self, page) -> None:
        await expect(page.locator(self._selector)).to_be_attached(**self._kwargs)

    @property
    def name(self) -> str:
        return "presence"