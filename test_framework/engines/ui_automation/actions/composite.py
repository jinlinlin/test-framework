"""
复合操作。

设计模式：命令模式（Command）+ 组合模式（Composite）
"""
from __future__ import annotations

from typing import Any, List

from .base import UIAction


class CompositeAction(UIAction):
    """复合操作"""

    def __init__(self, actions: List[UIAction], **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._actions = actions

    async def execute(self, page) -> None:
        for action in self._actions:
            await action.execute(page)

    @property
    def name(self) -> str:
        return "composite"