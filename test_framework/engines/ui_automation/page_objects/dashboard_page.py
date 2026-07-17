"""
仪表板页面 Page Object。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage
from .components.header import Header
from .components.sidebar import Sidebar


class DashboardPage(BasePage):
    """
    仪表板页面

    提供仪表板相关的操作和断言。
    """

    URL_PATH = "/dashboard"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)
        self._init_page()

    def _init_page(self) -> None:
        """初始化页面元素和组件"""
        self.header = Header(self._page)
        self.sidebar = Sidebar(self._page)

    async def wait_for_dashboard(self) -> "DashboardPage":
        """等待仪表板加载完成"""
        await self.wait_for_element('data-testid="dashboard-container"')
        return self

    async def get_welcome_message(self) -> str:
        """获取欢迎消息"""
        return await self.get_text('data-testid="welcome-message"')