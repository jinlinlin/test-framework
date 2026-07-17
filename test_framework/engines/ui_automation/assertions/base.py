"""
断言基类 - 策略模式

定义UI断言的统一接口。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page


class UIAssertion(ABC):
    """UI断言基类"""

    def __init__(self, selector: str = "", **kwargs: Any) -> None:
        self._selector = selector
        self._kwargs = kwargs

    @abstractmethod
    async def execute(self, page: Page) -> None:
        """
        执行断言

        Args:
            page: Playwright Page对象

        Raises:
            AssertionError: 断言失败时抛出
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """断言名称"""
        ...