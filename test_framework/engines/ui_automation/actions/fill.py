"""
填充操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any

from .base import UIAction


class FillAction(UIAction):
    """填充操作"""

    def __init__(self, selector: str, value: str, **kwargs: Any) -> None:
        super().__init__(selector, **kwargs)
        self._value = value

    async def execute(self, page) -> None:
        await page.fill(self._selector, self._value, **self._kwargs)

    @property
    def name(self) -> str:
        return "fill"