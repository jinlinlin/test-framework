"""
等待器基类 - 策略模式

定义等待策略的统一接口。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page


class WaiterStrategy(ABC):
    """等待策略基类"""

    def __init__(self, selector: str = "", **kwargs: Any) -> None:
        self._selector = selector
        self._kwargs = kwargs

    @abstractmethod
    async def wait(self, page: Page) -> None:
        """
        执行等待

        Args:
            page: Playwright Page对象
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...