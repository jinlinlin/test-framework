"""
模态框组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Modal(BaseComponent):
    """模态框组件"""

    ROOT_SELECTOR = ".modal"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def wait_for_open(self) -> "Modal":
        """等待模态框打开"""
        await self.wait_for_visible()
        return self

    async def wait_for_close(self) -> "Modal":
        """等待模态框关闭"""
        await self.wait_for_hidden()
        return self

    async def click_close(self) -> "Modal":
        """点击关闭按钮"""
        await self.click('[data-testid="modal-close"]')
        return self

    async def click_confirm(self) -> "Modal":
        """点击确认按钮"""
        await self.click('[data-testid="modal-confirm"]')
        return self

    async def click_cancel(self) -> "Modal":
        """点击取消按钮"""
        await self.click('[data-testid="modal-cancel"]')
        return self