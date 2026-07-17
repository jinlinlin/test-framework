"""
加载组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Loading(BaseComponent):
    """加载组件"""

    ROOT_SELECTOR = ".loading"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def wait_for_hide(self) -> "Loading":
        """等待加载完成（隐藏）"""
        await self.wait_for_hidden()
        return self