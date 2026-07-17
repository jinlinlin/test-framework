"""
Playwright 客户端 — 封装 Playwright API 的统一浏览器操作接口（适配器模式）。

设计模式：适配器模式
职责：将 Playwright 的异步 API 适配为框架统一接口，
      封装浏览器启动、页面创建、导航、截图等操作。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PlaywrightClient:
    """
    Playwright 适配器客户端。

    封装 Playwright 的底层 API，提供统一的浏览器操作接口，
    使引擎代码不直接依赖 Playwright 的具体 API。

    Attributes:
        _config: 浏览器配置。
        _playwright: Playwright 实例。
        _browser: 浏览器实例。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化 Playwright 客户端。

        Args:
            config: 浏览器配置（browser, headless, timeout, viewport 等）。
        """
        self._config = config
        self._playwright = None
        self._browser = None

    async def launch(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
    ) -> None:
        """
        启动浏览器。

        Args:
            browser_type: 浏览器类型（chromium / firefox / webkit）。
            headless: 是否无头模式。
        """
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            # 根据类型选择浏览器
            launcher = getattr(self._playwright, browser_type, self._playwright.chromium)
            self._browser = await launcher.launch(headless=headless)
            logger.info(f"浏览器已启动: {browser_type}, headless={headless}")

        except ImportError:
            logger.warning("Playwright 未安装，请运行: pip install playwright && playwright install")
            raise

    async def new_page(self, viewport: Optional[Dict[str, int]] = None) -> Any:
        """
        创建新页面。

        Args:
            viewport: 视口大小配置（width, height）。

        Returns:
            Playwright Page 对象。
        """
        if not self._browser:
            raise RuntimeError("浏览器未启动，请先调用 launch()")

        context = await self._browser.new_context()
        if viewport:
            await context.set_viewport_size(viewport)

        page = await context.new_page()
        return page

    async def goto(self, page: Any, url: str, wait_until: str = "networkidle") -> Any:
        """
        导航到指定 URL。

        Args:
            page: Playwright Page 对象。
            url: 目标 URL。
            wait_until: 等待策略（load / domcontentloaded / networkidle）。

        Returns:
            Response 对象。
        """
        timeout = self._config.get("timeout", 30000)
        response = await page.goto(url, wait_until=wait_until, timeout=timeout)
        logger.debug(f"页面导航完成: {url}")
        return response

    async def screenshot(self, page: Any, path: str) -> str:
        """
        页面截图。

        Args:
            page: Playwright Page 对象。
            path: 截图保存路径。

        Returns:
            截图文件路径。
        """
        await page.screenshot(path=path, full_page=True)
        logger.debug(f"页面截图已保存: {path}")
        return path

    async def evaluate(self, page: Any, expression: str) -> Any:
        """
        在页面中执行 JavaScript 表达式。

        Args:
            page: Playwright Page 对象。
            expression: JavaScript 表达式字符串。

        Returns:
            执行结果。
        """
        return await page.evaluate(expression)

    async def close_page(self, page: Any) -> None:
        """
        关闭页面。

        Args:
            page: Playwright Page 对象。
        """
        try:
            await page.context.close()
        except Exception:
            pass

    async def close(self) -> None:
        """关闭浏览器和 Playwright 实例。"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.debug("Playwright 已关闭")
