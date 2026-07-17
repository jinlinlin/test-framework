"""
元素数量断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class CountAssertion(UIAssertion):
    """元素数量断言"""

    def __init__(self, selector: str, expected_count: int, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._expected_count = expected_count

    async def execute(self, page) -> None:
        await expect(page.locator(self._selector)).to_have_count(self._expected_count, **self._kwargs)

    @property
    def name(self) -> str:
        return "count"