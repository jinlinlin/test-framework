"""
用户列表页面。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage


class UserListPage(BasePage):
    """用户列表页面"""

    URL_PATH = "/users"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)

    async def click_create_user(self) -> "UserListPage":
        """点击创建用户按钮"""
        await self.click('[data-testid="create-user-btn"]')
        return self

    async def search_user(self, keyword: str) -> "UserListPage":
        """搜索用户"""
        await self.fill('[data-testid="user-search"]', keyword)
        await self.press('[data-testid="user-search"]', "Enter")
        return self

    async def get_user_count(self) -> int:
        """获取用户数量"""
        count_text = await self.get_text('[data-testid="user-count"]')
        return int(count_text) if count_text.isdigit() else 0