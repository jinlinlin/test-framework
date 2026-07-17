"""
页面头部组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Header(BaseComponent):
    """页面头部组件"""

    ROOT_SELECTOR = "header"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def click_logo(self) -> "Header":
        """点击Logo"""
        await self.click('data-testid="logo"')
        return self

    async def click_user_menu(self) -> "Header":
        """点击用户菜单"""
        await self.click('data-testid="user-menu"')
        return self

    async def click_notifications(self) -> "Header":
        """点击通知按钮"""
        await self.click('data-testid="notifications"')
        return self

    async def get_user_name(self) -> str:
        """获取用户名"""
        return await self.get_text('data-testid="user-name"')