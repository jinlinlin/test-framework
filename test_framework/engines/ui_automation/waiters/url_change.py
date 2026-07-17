"""
等待URL变化策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import WaiterStrategy


class URLChangeWaiter(WaiterStrategy):
    """等待URL变化策略"""

    def __init__(self, selector: str = "", url_pattern: str = "", **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._url_pattern = url_pattern

    async def wait(self, page) -> None:
        await expect(page).to_have_url(self._url_pattern, **self._kwargs)

    @property
    def name(self) -> str:
        return "url_change"