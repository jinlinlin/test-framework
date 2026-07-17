"""
登录页面 Page Object。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage


class LoginPage(BasePage):
    """
    登录页面

    提供登录相关的操作和断言。
    """

    URL_PATH = "/login"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)
        self._init_page()

    def _init_page(self) -> None:
        """初始化页面元素定位器"""
        self.username_input = self.locate_by_test_id("username")
        self.password_input = self.locate_by_test_id("password")
        self.login_button = self.locate_by_test_id("login-btn")
        self.error_message = self.locate_by_test_id("error-message")

    async def enter_username(self, username: str) -> "LoginPage":
        """输入用户名"""
        await self.fill('input[name="username"]', username)
        return self

    async def enter_password(self, password: str) -> "LoginPage":
        """输入密码"""
        await self.fill('input[name="password"]', password)
        return self

    async def click_login(self) -> "LoginPage":
        """点击登录按钮"""
        await self.click('button[type="submit"]')
        return self

    async def login(self, username: str, password: str) -> "LoginPage":
        """执行完整登录流程"""
        await self.enter_username(username)
        await self.enter_password(password)
        await self.click_login()
        return self

    async def should_have_error_message(self, message: str) -> "LoginPage":
        """断言错误消息"""
        await self.assert_text(self.error_message, message)
        return self