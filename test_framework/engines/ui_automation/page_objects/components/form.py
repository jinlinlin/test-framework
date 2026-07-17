"""
表单组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from typing import Dict

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Form(BaseComponent):
    """表单组件"""

    ROOT_SELECTOR = "form"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def fill_fields(self, data: Dict[str, str]) -> "Form":
        """填充多个字段"""
        for field_name, value in data.items():
            await self.fill(f'[name="{field_name}"]', value)
        return self

    async def submit(self) -> "Form":
        """提交表单"""
        await self.click('button[type="submit"]')
        return self