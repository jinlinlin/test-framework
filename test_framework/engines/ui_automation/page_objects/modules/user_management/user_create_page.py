"""
用户创建页面。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage


class UserCreatePage(BasePage):
    """用户创建页面"""

    URL_PATH = "/users/create"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)

    async def fill_form(self, username: str, email: str, password: str) -> "UserCreatePage":
        """填充创建表单"""
        await self.fill('[name="username"]', username)
        await self.fill('[name="email"]', email)
        await self.fill('[name="password"]', password)
        return self

    async def submit(self) -> "UserCreatePage":
        """提交表单"""
        await self.click('button[type="submit"]')
        return self