"""
订单列表页面。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage


class OrderListPage(BasePage):
    """订单列表页面"""

    URL_PATH = "/orders"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)

    async def search_order(self, order_id: str) -> "OrderListPage":
        """搜索订单"""
        await self.fill('[data-testid="order-search"]', order_id)
        await self.press('[data-testid="order-search"]', "Enter")
        return self