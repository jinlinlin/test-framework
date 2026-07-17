"""
表格组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Table(BaseComponent):
    """表格组件"""

    ROOT_SELECTOR = "table"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def get_row_count(self) -> int:
        """获取行数"""
        rows = await self.find_elements("tbody tr")
        return len(rows)

    async def get_cell_value(self, row_index: int, column_index: int) -> str:
        """获取单元格值"""
        cell = self.locate(f"tbody tr:nth-child({row_index + 1}) td:nth-child({column_index + 1})")
        return await cell.text_content() or ""