"""
聚焦操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class FocusAction(UIAction):
    """聚焦操作"""

    async def execute(self, page) -> None:
        await page.focus(self._selector, **self._kwargs)

    @property
    def name(self) -> str:
        return "focus"