"""
复合定位策略。

设计模式：策略模式（Strategy）+ 组合模式（Composite）
"""
from __future__ import annotations

from typing import Any, List

from playwright.async_api import Locator, Page

from .base import LocatorStrategy


class CompositeLocator(LocatorStrategy):
    """复合定位策略"""

    def __init__(self, strategies: List[LocatorStrategy]) -> None:
        self._strategies = strategies

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        """依次尝试多个定位策略，返回第一个成功的"""
        for strategy in self._strategies:
            try:
                locator = strategy.locate(page, value, **kwargs)
                return locator
            except Exception:
                continue
        raise ValueError(f"Failed to locate element with value: {value}")

    @property
    def name(self) -> str:
        return "composite"