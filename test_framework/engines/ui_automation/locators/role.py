"""
ARIA role定位策略。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from typing import Any, Optional

from playwright.async_api import Locator, Page

from .base import LocatorStrategy


class RoleLocator(LocatorStrategy):
    """ARIA role定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        name = kwargs.pop("name", None)
        return page.get_by_role(value, name=name, **kwargs)

    @property
    def name(self) -> str:
        return "role"