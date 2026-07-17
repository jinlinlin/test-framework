"""
启用状态断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class EnabledAssertion(UIAssertion):
    """启用状态断言"""

    def __init__(self, selector: str, enabled: bool = True, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._enabled = enabled

    async def execute(self, page) -> None:
        if self._enabled:
            await expect(page.locator(self._selector)).to_be_enabled(**self._kwargs)
        else:
            await expect(page.locator(self._selector)).to_be_disabled(**self._kwargs)

    @property
    def name(self) -> str:
        return "enabled"