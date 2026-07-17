"""
URL断言。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from playwright.async_api import expect

from .base import UIAssertion


class URLAssertion(UIAssertion):
    """URL断言"""

    def __init__(self, url_pattern: str, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._url_pattern = url_pattern

    async def execute(self, page) -> None:
        await expect(page).to_have_url(self._url_pattern, **self._kwargs)

    @property
    def name(self) -> str:
        return "url"