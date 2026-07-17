"""
失焦操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from .base import UIAction


class BlurAction(UIAction):
    """失焦操作"""

    async def execute(self, page) -> None:
        await page.evaluate(f'document.querySelector("{self._selector}").blur()')

    @property
    def name(self) -> str:
        return "blur"