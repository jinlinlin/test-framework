"""
页面底部组件。

设计模式：组合模式（Composite）
"""
from __future__ import annotations

from playwright.async_api import Page

from ...core.playwright import BaseComponent


class Footer(BaseComponent):
    """页面底部组件"""

    ROOT_SELECTOR = "footer"

    def __init__(self, page: Page) -> None:
        super().__init__(page)