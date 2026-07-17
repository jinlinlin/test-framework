"""
按键操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any

from .base import UIAction


class PressAction(UIAction):
    """按键操作"""

    def __init__(self, selector: str, key: str, **kwargs: Any) -> None:
        super().__init__(selector, **kwargs)
        self._key = key

    async def execute(self, page) -> None:
        await page.locator(self._selector).press(self._key, **self._kwargs)

    @property
    def name(self) -> str:
        return "press"