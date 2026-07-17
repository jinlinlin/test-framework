"""
右键点击操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class RightClickAction(UIAction):
    """右键点击操作"""

    async def execute(self, page) -> None:
        await page.click(self._selector, button="right", **self._kwargs)

    @property
    def name(self) -> str:
        return "rightclick"