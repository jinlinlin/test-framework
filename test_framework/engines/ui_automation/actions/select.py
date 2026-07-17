"""
下拉选择操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any, List, Union

from .base import UIAction


class SelectAction(UIAction):
    """下拉选择操作"""

    def __init__(self, selector: str, value: Union[str, List[str]], **kwargs: Any) -> None:
        super().__init__(selector, **kwargs)
        self._value = value

    async def execute(self, page) -> None:
        await page.select_option(self._selector, self._value, **self._kwargs)

    @property
    def name(self) -> str:
        return "select"