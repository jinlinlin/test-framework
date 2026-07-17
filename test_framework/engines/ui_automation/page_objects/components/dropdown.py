"""
下拉菜单组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Dropdown(BaseComponent):
    """下拉菜单组件"""

    ROOT_SELECTOR = ".dropdown"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def select(self, option_text: str) -> "Dropdown":
        """选择选项"""
        await self.click('[data-testid="dropdown-toggle"]')
        await self.click(f'[data-testid="dropdown-option-{option_text}"]')
        return self