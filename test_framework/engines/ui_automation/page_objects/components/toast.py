"""
提示消息组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Toast(BaseComponent):
    """提示消息组件"""

    ROOT_SELECTOR = ".toast"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def wait_for_show(self) -> "Toast":
        """等待显示"""
        await self.wait_for_visible()
        return self

    async def get_message(self) -> str:
        """获取消息内容"""
        return await self.get_text('[data-testid="toast-message"]')