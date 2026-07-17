"""
上下文管理器。

封装浏览器上下文的创建、配置和管理。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class ContextManager:
    """
    上下文管理器

    封装浏览器上下文的创建、配置和管理。
    """

    def __init__(self, browser: Browser) -> None:
        self._browser = browser
        self._context: Optional[BrowserContext] = None
        self._pages: list[Page] = []

    async def create_context(self, **kwargs: Any) -> BrowserContext:
        """
        创建浏览器上下文

        Args:
            **kwargs: 上下文配置参数

        Returns:
            浏览器上下文
        """
        self._context = await self._browser.new_context(**kwargs)
        logger.info("Browser context created")
        return self._context

    async def close_context(self) -> None:
        """关闭上下文"""
        for page in self._pages:
            try:
                await page.close()
            except Exception as e:
                logger.warning(f"Error closing page: {e}")

        if self._context:
            await self._context.close()
            self._context = None
            logger.info("Browser context closed")

    async def new_page(self) -> Page:
        """创建新页面"""
        if not self._context:
            raise RuntimeError("No browser context available")

        page = await self._context.new_page()
        self._pages.append(page)
        return page

    @property
    def context(self) -> Optional[BrowserContext]:
        """获取上下文"""
        return self._context