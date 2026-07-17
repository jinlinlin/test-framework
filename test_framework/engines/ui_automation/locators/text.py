"""
文本定位策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Locator, Page

from .base import LocatorStrategy


class TextLocator(LocatorStrategy):
    """文本定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        exact = kwargs.pop("exact", False)
        return page.get_by_text(value, exact=exact, **kwargs)

    @property
    def name(self) -> str:
        return "text"