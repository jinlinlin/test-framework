"""
标签页组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Tabs(BaseComponent):
    """标签页组件"""

    ROOT_SELECTOR = ".tabs"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def select_tab(self, tab_name: str) -> "Tabs":
        """选择标签页"""
        await self.click(f'[data-testid="tab-{tab_name}"]')
        return self