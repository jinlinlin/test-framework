"""
勾选操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class CheckAction(UIAction):
    """勾选操作"""

    async def execute(self, page) -> None:
        await page.check(self._selector, **self._kwargs)

    @property
    def name(self) -> str:
        return "check"