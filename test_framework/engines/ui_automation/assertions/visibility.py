"""
可见性断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class VisibilityAssertion(UIAssertion):
    """可见性断言"""

    def __init__(self, selector: str, visible: bool = True, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._visible = visible

    async def execute(self, page) -> None:
        if self._visible:
            await expect(page.locator(self._selector)).to_be_visible(**self._kwargs)
        else:
            await expect(page.locator(self._selector)).to_be_hidden(**self._kwargs)

    @property
    def name(self) -> str:
        return "visibility"