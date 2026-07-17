"""
基于 Playwright 的浏览器适配器。

特点：
- 支持 Chromium / Firefox / WebKit 三种引擎
- 原生异步支持
- 自动等待元素可操作
- 网络请求拦截与记录
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .adapter import BrowserAdapter, NetworkEntry, PageElement, PageScreenshot

logger = logging.getLogger(__name__)


class PlaywrightAdapter(BrowserAdapter):
    """
    Playwright 浏览器适配器。

    通过 playwright.async_api 实现浏览器自动化操作，
    支持多浏览器引擎、网络拦截、截图等功能。

    配置项::

        {
            "browser_type": "chromium",      # chromium / firefox / webkit
            "headless": True,                 # 是否无头模式
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "...",
            "slow_mo": 0,                    # 操作间延迟（ms）
            "timeout": 30000,                # 默认超时（ms）
            "record_network": True,          # 是否记录网络请求
        }
    """

    @property
    def implementation_name(self) -> str:
        return "playwright"

    def __init__(self) -> None:
        """初始化 Playwright 适配器。"""
        self._playwright: Optional[Any] = None  # playwright 实例
        self._browser: Optional[Any] = None  # Browser 实例
        self._context: Optional[Any] = None  # BrowserContext 实例
        self._page: Optional[Any] = None  # Page 实例
        self._network_entries: List[NetworkEntry] = []  # 网络请求记录
        self._record_network: bool = True  # 是否记录网络请求

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        启动浏览器并创建上下文。

        Args:
            config: 配置字典，包含浏览器类型、无头模式等选项。
        """
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        browser_type = config.get("browser_type", "chromium")
        headless = config.get("headless", True)
        slow_mo = config.get("slow_mo", 0)

        # 选择浏览器引擎
        launcher = getattr(self._playwright, browser_type)
        self._browser = await launcher.launch(headless=headless, slow_mo=slow_mo)

        # 创建浏览器上下文
        viewport = config.get("viewport", {"width": 1280, "height": 720})
        user_agent = config.get("user_agent")
        self._context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
        )

        # 设置默认超时
        timeout = config.get("timeout", 30000)
        self._context.set_default_timeout(timeout)

        # 创建默认页面
        self._page = await self._context.new_page()
        self._record_network = config.get("record_network", True)

        # 注册网络请求监听
        if self._record_network:
            self._page.on("response", self._on_response)

        logger.debug(
            f"PlaywrightAdapter 已连接: browser={browser_type}, headless={headless}"
        )

    async def disconnect(self) -> None:
        """关闭浏览器并释放资源。"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None
        self._network_entries.clear()
        logger.debug("PlaywrightAdapter 已断开")

    async def is_connected(self) -> bool:
        return self._browser is not None and self._page is not None

    # ===== 内部辅助 =====

    def _on_response(self, response: Any) -> None:
        """网络响应回调，记录请求信息。"""
        try:
            request = response.request
            entry = NetworkEntry(
                url=response.url,
                method=request.method,
                status=response.status,
                resource_type=request.resource_type,
                size=-1,  # 异步获取 size 不便在此处完成
            )
            self._network_entries.append(entry)
        except Exception as e:
            logger.debug(f"记录网络请求失败: {e}")

    def _ensure_page(self) -> Any:
        """确保页面可用，否则抛出异常。"""
        if not self._page:
            raise RuntimeError("PlaywrightAdapter 未连接或页面不可用")
        return self._page

    # ===== 页面导航 =====

    async def goto(self, url: str, wait_until: str = "load") -> None:
        page = self._ensure_page()
        await page.goto(url, wait_until=wait_until)

    async def get_url(self) -> str:
        page = self._ensure_page()
        return page.url

    async def get_title(self) -> str:
        page = self._ensure_page()
        return await page.title()

    # ===== 元素交互 =====

    async def click(self, selector: str, **kwargs: Any) -> None:
        page = self._ensure_page()
        force = kwargs.get("force", False)
        timeout = kwargs.get("timeout")
        await page.click(selector, force=force, timeout=timeout)

    async def fill(self, selector: str, value: str) -> None:
        page = self._ensure_page()
        await page.fill(selector, value)

    async def select_option(self, selector: str, value: str) -> None:
        page = self._ensure_page()
        await page.select_option(selector, value)

    async def hover(self, selector: str) -> None:
        page = self._ensure_page()
        await page.hover(selector)

    # ===== 元素查询 =====

    async def query_selector(self, selector: str) -> Optional[PageElement]:
        page = self._ensure_page()
        element = await page.query_selector(selector)
        if not element:
            return None
        return await self._to_page_element(element)

    async def query_selector_all(self, selector: str) -> List[PageElement]:
        page = self._ensure_page()
        elements = await page.query_selector_all(selector)
        result = []
        for elem in elements:
            result.append(await self._to_page_element(elem))
        return result

    async def _to_page_element(self, element: Any) -> PageElement:
        """将 Playwright ElementHandle 转换为 PageElement。"""
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        text = await element.inner_text()
        inner_html = await element.inner_html()
        is_visible = await element.is_visible()
        bounding_box = await element.bounding_box()
        # 获取所有属性
        attributes = await element.evaluate(
            "el => Object.fromEntries([...el.attributes].map(a => [a.name, a.value]))"
        )
        return PageElement(
            tag_name=tag_name,
            text=text,
            attributes=attributes,
            inner_html=inner_html,
            is_visible=is_visible,
            bounding_box=bounding_box,
        )

    async def wait_for_selector(self, selector: str, timeout: float = 30.0) -> None:
        page = self._ensure_page()
        await page.wait_for_selector(selector, timeout=timeout * 1000)

    # ===== 截图与脚本 =====

    async def screenshot(self, path: str = "", full_page: bool = False) -> PageScreenshot:
        page = self._ensure_page()
        kwargs: Dict[str, Any] = {"full_page": full_page}
        if path:
            kwargs["path"] = path
        data = await page.screenshot(**kwargs)
        viewport_size = page.viewport_size or {"width": 0, "height": 0}
        return PageScreenshot(
            data=data,
            path=path,
            width=viewport_size.get("width", 0),
            height=viewport_size.get("height", 0),
        )

    async def evaluate(self, script: str) -> Any:
        page = self._ensure_page()
        return await page.evaluate(script)

    # ===== 网络拦截 =====

    async def get_network_entries(self) -> List[NetworkEntry]:
        return list(self._network_entries)

    # ===== 页面管理 =====

    async def new_page(self) -> None:
        if not self._context:
            raise RuntimeError("PlaywrightAdapter 未连接")
        # 取消旧页面监听
        if self._page and self._record_network:
            self._page.remove_listener("response", self._on_response)
        self._page = await self._context.new_page()
        if self._record_network:
            self._page.on("response", self._on_response)

    async def close_page(self) -> None:
        if self._page:
            await self._page.close()
            self._page = None

    async def get_cookies(self) -> List[Dict[str, Any]]:
        if not self._context:
            return []
        return await self._context.cookies()

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        if not self._context:
            raise RuntimeError("PlaywrightAdapter 未连接")
        await self._context.add_cookies(cookies)

    async def clear_cookies(self) -> None:
        if self._context:
            await self._context.clear_cookies()
