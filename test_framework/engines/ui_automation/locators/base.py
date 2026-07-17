"""
定位器基类 - 策略模式

定义定位策略的统一接口。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Locator, Page


class LocatorStrategy(ABC):
    """定位策略基类"""

    @abstractmethod
    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        """
        执行元素定位

        Args:
            page: Playwright Page对象
            value: 定位值
            **kwargs: 额外参数

        Returns:
            定位器
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...