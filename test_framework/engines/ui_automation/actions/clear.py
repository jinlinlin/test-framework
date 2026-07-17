"""
清空操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class ClearAction(UIAction):
    """清空操作"""

    async def execute(self, page) -> None:
        await page.fill(self._selector, "")

    @property
    def name(self) -> str:
        return "clear"