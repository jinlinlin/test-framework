"""
分页组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Pagination(BaseComponent):
    """分页组件"""

    ROOT_SELECTOR = ".pagination"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def go_to_page(self, page_number: int) -> "Pagination":
        """跳转到指定页码"""
        await self.click(f'[data-testid="page-{page_number}"]')
        return self

    async def next_page(self) -> "Pagination":
        """下一页"""
        await self.click('[data-testid="pagination-next"]')
        return self

    async def previous_page(self) -> "Pagination":
        """上一页"""
        await self.click('[data-testid="pagination-previous"]')
        return self