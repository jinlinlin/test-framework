"""
拖拽操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any

from .base import UIAction


class DragAction(UIAction):
    """拖拽操作"""

    def __init__(self, source_selector: str, target_selector: str, **kwargs: Any) -> None:
        super().__init__(source_selector, **kwargs)
        self._target_selector = target_selector

    async def execute(self, page) -> None:
        await page.drag_and_drop(self._selector, self._target_selector, **self._kwargs)

    @property
    def name(self) -> str:
        return "drag"