"""
placeholder定位策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Locator, Page

from .base import LocatorStrategy


class PlaceholderLocator(LocatorStrategy):
    """placeholder定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.get_by_placeholder(value, **kwargs)

    @property
    def name(self) -> str:
        return "placeholder"