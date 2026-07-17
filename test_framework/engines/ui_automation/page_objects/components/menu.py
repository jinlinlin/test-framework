"""
菜单组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Menu(BaseComponent):
    """菜单组件"""

    ROOT_SELECTOR = ".menu"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def click_item(self, item_name: str) -> "Menu":
        """点击菜单项"""
        await self.click(f'[data-testid="menu-item-{item_name}"]')
        return self