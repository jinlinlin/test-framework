"""
CSS属性断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from .base import UIAssertion


class CSSPropertyAssertion(UIAssertion):
    """CSS属性断言"""

    def __init__(self, selector: str, property_name: str, expected_value: str, **kwargs) -> None:
        super().__init__(selector, **kwargs)
        self._property_name = property_name
        self._expected_value = expected_value

    async def execute(self, page) -> None:
        locator = page.locator(self._selector)
        await locator.wait_for(state="visible", **self._kwargs)
        computed_style = await locator.evaluate(
            f'(el) => window.getComputedStyle(el).getPropertyValue("{self._property_name}")'
        )
        assert computed_style == self._expected_value, (
            f"Expected CSS {self._property_name} to be {self._expected_value}, got {computed_style}"
        )

    @property
    def name(self) -> str:
        return "css_property"