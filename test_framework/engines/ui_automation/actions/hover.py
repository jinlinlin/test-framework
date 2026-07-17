"""
悬停操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class HoverAction(UIAction):
    """悬停操作"""

    async def execute(self, page) -> None:
        await page.hover(self._selector, **self._kwargs)

    @property
    def name(self) -> str:
        return "hover"