"""
等待文本变化策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import WaiterStrategy


class TextChangeWaiter(WaiterStrategy):
    """等待文本变化策略"""

    def __init__(self, selector: str, expected_text: str, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._expected_text = expected_text

    async def wait(self, page) -> None:
        await expect(page.locator(self._selector)).to_have_text(self._expected_text, **self._kwargs)

    @property
    def name(self) -> str:
        return "text_change"