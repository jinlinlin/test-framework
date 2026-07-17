"""
侧边栏组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Sidebar(BaseComponent):
    """侧边栏组件"""

    ROOT_SELECTOR = "aside"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def navigate_to(self, menu_item: str) -> "Sidebar":
        """导航到指定菜单项"""
        await self.click(f'[data-testid="{menu_item}"]')
        return self

    async def click_dashboard(self) -> "Sidebar":
        """点击仪表板"""
        return await self.navigate_to("menu-dashboard")

    async def click_users(self) -> "Sidebar":
        """点击用户管理"""
        return await self.navigate_to("menu-users")

    async def click_orders(self) -> "Sidebar":
        """点击订单管理"""
        return await self.navigate_to("menu-orders")

    async def click_reports(self) -> "Sidebar":
        """点击报表"""
        return await self.navigate_to("menu-reports")