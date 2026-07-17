"""
等待操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any

from .base import UIAction


class WaitAction(UIAction):
    """等待操作"""

    async def execute(self, page) -> None:
        await page.wait_for_selector(self._selector, **self._kwargs)

    @property
    def name(self) -> str:
        return "wait"