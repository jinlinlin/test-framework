"""
用户编辑页面。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage


class UserEditPage(BasePage):
    """用户编辑页面"""

    URL_PATH = "/users/edit"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)

    async def update_email(self, email: str) -> "UserEditPage":
        """更新邮箱"""
        await self.fill('[name="email"]', email)
        return self

    async def submit(self) -> "UserEditPage":
        """提交表单"""
        await self.click('button[type="submit"]')
        return self