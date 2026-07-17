"""
复合断言。

设计模式：策略模式（Strategy）+ 组合模式（Composite）
"""
from __future__ import annotations

from typing import List

from .base import UIAssertion


class CompositeAssertion(UIAssertion):
    """复合断言"""

    def __init__(self, assertions: List[UIAssertion], **kwargs) -> None:
        super().__init__("", **kwargs)
        self._assertions = assertions

    async def execute(self, page) -> None:
        for assertion in self._assertions:
            await assertion.execute(page)

    @property
    def name(self) -> str:
        return "composite"