"""
逐字输入操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any

from .base import UIAction


class TypeAction(UIAction):
    """逐字输入操作"""

    def __init__(self, selector: str, value: str, delay: int = 50, **kwargs: Any) -> None:
        super().__init__(selector, **kwargs)
        self._value = value
        self._delay = delay

    async def execute(self, page) -> None:
        await page.type(self._selector, self._value, delay=self._delay, **self._kwargs)

    @property
    def name(self) -> str:
        return "type"