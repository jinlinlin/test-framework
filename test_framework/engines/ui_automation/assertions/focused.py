"""
聚焦状态断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class FocusedAssertion(UIAssertion):
    """聚焦状态断言"""

    async def execute(self, page) -> None:
        await expect(page.locator(self._selector)).to_be_focused(**self._kwargs)

    @property
    def name(self) -> str:
        return "focused"