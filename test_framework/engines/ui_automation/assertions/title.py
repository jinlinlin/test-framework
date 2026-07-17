"""
标题断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class TitleAssertion(UIAssertion):
    """标题断言"""

    def __init__(self, expected_title: str, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._expected_title = expected_title

    async def execute(self, page) -> None:
        await expect(page).to_have_title(self._expected_title, **self._kwargs)

    @property
    def name(self) -> str:
        return "title"