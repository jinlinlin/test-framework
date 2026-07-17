"""
勾选状态断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class CheckedAssertion(UIAssertion):
    """勾选状态断言"""

    def __init__(self, selector: str, checked: bool = True, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._checked = checked

    async def execute(self, page) -> None:
        if self._checked:
            await expect(page.locator(self._selector)).to_be_checked(**self._kwargs)
        else:
            await expect(page.locator(self._selector)).not_to_be_checked(**self._kwargs)

    @property
    def name(self) -> str:
        return "checked"