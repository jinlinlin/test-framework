"""
滚动操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class ScrollAction(UIAction):
    """滚动操作"""

    async def execute(self, page) -> None:
        await page.locator(self._selector).scroll_into_view_if_needed(**self._kwargs)

    @property
    def name(self) -> str:
        return "scroll"