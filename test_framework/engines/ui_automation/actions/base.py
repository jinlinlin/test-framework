"""
UI操作基类 - 命令模式

定义UI操作的统一接口。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page


class UIAction(ABC):
    """UI操作基类"""

    def __init__(self, selector: str, **kwargs: Any) -> None:
        self._selector = selector
        self._kwargs = kwargs

    @abstractmethod
    async def execute(self, page: Page) -> None:
        """
        执行操作

        Args:
            page: Playwright Page对象
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """操作名称"""
        ...