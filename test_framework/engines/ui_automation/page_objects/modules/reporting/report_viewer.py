"""
报表查看器页面。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from ...core.playwright import BasePage


class ReportViewer(BasePage):
    """报表查看器页面"""

    URL_PATH = "/reports"

    def __init__(self, page: Page, base_url: Optional[str] = None) -> None:
        super().__init__(page, base_url)

    async def select_report(self, report_name: str) -> "ReportViewer":
        """选择报表"""
        await self.click(f'[data-testid="report-{report_name}"]')
        return self