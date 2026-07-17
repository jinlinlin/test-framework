"""
截图操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any, Optional

from .base import UIAction


class ScreenshotAction(UIAction):
    """截图操作"""

    def __init__(self, selector: str = "", path: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(selector, **kwargs)
        self._path = path

    async def execute(self, page) -> None:
        if self._selector:
            await page.locator(self._selector).screenshot(path=self._path, **self._kwargs)
        else:
            await page.screenshot(path=self._path, **self._kwargs)

    @property
    def name(self) -> str:
        return "screenshot"