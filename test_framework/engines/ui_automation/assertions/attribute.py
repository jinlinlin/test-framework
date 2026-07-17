"""
属性断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class AttributeAssertion(UIAssertion):
    """属性断言"""

    def __init__(self, selector: str, attribute: str, expected_value: str, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._attribute = attribute
        self._expected_value = expected_value

    async def execute(self, page) -> None:
        await expect(page.locator(self._selector)).to_have_attribute(
            self._attribute, self._expected_value, **self._kwargs
        )

    @property
    def name(self) -> str:
        return "attribute"