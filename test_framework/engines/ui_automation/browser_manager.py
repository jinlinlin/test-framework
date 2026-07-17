"""
浏览器管理器。

封装浏览器的创建、配置和管理。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserType, Playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    浏览器管理器

    封装浏览器的创建、配置和管理。
    """

    def __init__(self, playwright: Playwright) -> None:
        self._playwright = playwright
        self._browser: Optional[Browser] = None

    async def launch_browser(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
        slow_mo: int = 0,
        **kwargs: Any
    ) -> Browser:
        """
        启动浏览器

        Args:
            browser_type: 浏览器类型
            headless: 是否无头模式
            slow_mo: 操作延迟(ms)
            **kwargs: 额外参数

        Returns:
            浏览器实例
        """
        launcher = getattr(self._playwright, browser_type)
        self._browser = await launcher.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
            ],
            **kwargs
        )
        logger.info(f"Browser launched: {browser_type} (headless={headless})")
        return self._browser

    async def close_browser(self) -> None:
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.info("Browser closed")

    @property
    def browser(self) -> Optional[Browser]:
        """获取浏览器实例"""
        return self._browser