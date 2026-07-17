"""
Playwright管理器 - 单例模式

管理浏览器实例、上下文、页面的生命周期。

设计模式：单例模式（Singleton）
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Request, Response

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    device_scale_factor: float = 1.0
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"
    permissions: List[str] = field(default_factory=list)
    downloads_path: Optional[str] = None
    user_agent: Optional[str] = None
    ignore_https_errors: bool = False
    slow_mo: int = 0
    record_video_dir: Optional[str] = None
    record_har_path: Optional[str] = None
    trace_dir: Optional[str] = None
    screenshot_on_failure: bool = True
    video_on_failure: bool = True


class PlaywrightManager:
    """
    Playwright管理器 - 单例模式

    管理浏览器生命周期，提供页面和上下文管理能力。
    """

    _instance: Optional["PlaywrightManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "PlaywrightManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._current_page: Optional[Page] = None
        self._config = BrowserConfig()
        self._contexts: List[BrowserContext] = []
        self._pages: List[Page] = []

    @classmethod
    async def get_instance(cls) -> "PlaywrightManager":
        """获取单例实例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    async def initialize(self, config: Optional[BrowserConfig] = None) -> None:
        """初始化Playwright"""
        if config:
            self._config = config

        self._playwright = await self._launch_playwright()
        self._browser = await self._launch_browser()
        self._context = await self._create_context()
        self._current_page = await self._create_page()

        logger.info("Playwright initialized successfully")

    async def _launch_playwright(self) -> Playwright:
        """启动Playwright"""
        from playwright.async_api import async_playwright
        playwright = await async_playwright().start()
        return playwright

    async def _launch_browser(self) -> Browser:
        """启动浏览器"""
        browser = await self._playwright.chromium.launch(
            headless=self._config.headless,
            slow_mo=self._config.slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
            ]
        )
        return browser

    async def _create_context(self) -> BrowserContext:
        """创建浏览器上下文"""
        context = await self._browser.new_context(
            viewport=self._config.viewport,
            device_scale_factor=self._config.device_scale_factor,
            locale=self._config.locale,
            timezone_id=self._config.timezone_id,
            permissions=self._config.permissions,
            downloads_path=self._config.downloads_path,
            user_agent=self._config.user_agent,
            ignore_https_errors=self._config.ignore_https_errors,
            record_video_dir=self._config.record_video_dir,
            record_har_path=self._config.record_har_path,
        )
        self._contexts.append(context)
        return context

    async def _create_page(self) -> Page:
        """创建页面"""
        page = await self._context.new_page()
        self._pages.append(page)

        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(30000)

        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("console", self._on_console)
        page.on("dialog", self._on_dialog)
        page.on("pageerror", self._on_page_error)

        return page

    async def close(self) -> None:
        """关闭所有资源"""
        for page in self._pages:
            try:
                await page.close()
            except Exception as e:
                logger.warning(f"Error closing page: {e}")

        for context in self._contexts:
            try:
                await context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")

        logger.info("Playwright closed successfully")

    def reset(self) -> None:
        """重置单例（用于测试）"""
        self._instance = None

    async def new_page(self) -> Page:
        """创建新页面"""
        page = await self._context.new_page()
        self._pages.append(page)
        return page

    async def switch_to_page(self, index: int) -> Page:
        """切换到指定页面"""
        if 0 <= index < len(self._pages):
            self._current_page = self._pages[index]
            return self._current_page
        raise IndexError(f"Page index {index} out of range")

    @property
    def current_page(self) -> Page:
        """获取当前页面"""
        if not self._current_page:
            raise RuntimeError("No current page available")
        return self._current_page

    async def new_context(self, **kwargs: Any) -> BrowserContext:
        """创建新上下文"""
        context = await self._browser.new_context(**kwargs)
        self._contexts.append(context)
        return context

    async def switch_context(self, context: BrowserContext) -> None:
        """切换上下文"""
        self._context = context
        self._current_page = context.pages[0] if context.pages else await context.new_page()

    def _on_request(self, request: Request) -> None:
        """请求事件"""
        logger.debug(f"Request: {request.method} {request.url}")

    def _on_response(self, response: Response) -> None:
        """响应事件"""
        logger.debug(f"Response: {response.status} {response.url}")

    def _on_console(self, msg: Any) -> None:
        """控制台事件"""
        logger.debug(f"Console: {msg.type} - {msg.text}")

    def _on_dialog(self, dialog: Any) -> None:
        """对话框事件"""
        logger.warning(f"Dialog: {dialog.type} - {dialog.message}")
        dialog.accept()

    def _on_page_error(self, error: Any) -> None:
        """页面错误事件"""
        logger.error(f"Page error: {error}")

    async def start_trace(self, name: str = "trace") -> None:
        """开始追踪"""
        if self._context:
            await self._context.tracing.start(
                name=name,
                screenshots=True,
                snapshots=True,
                sources=True
            )

    async def stop_trace(self, path: str) -> None:
        """停止追踪"""
        if self._context:
            await self._context.tracing.stop(path=path)

    async def start_har(self, path: str) -> None:
        """开始录制HAR"""
        if self._context:
            await self._context.route_from_har(path)

    async def screenshot(self, path: str, full_page: bool = True) -> bytes:
        """截图"""
        return await self.current_page.screenshot(path=path, full_page=full_page)

    async def emulate_device(self, device_name: str) -> None:
        """模拟设备"""
        from playwright.async_api import devices
        device = devices.get(device_name)
        if device:
            await self._context.set_viewport_size(device["viewport"])
            await self._context.add_init_script(
                f'Object.defineProperty(navigator, "userAgent", {{ value: "{device["user_agent"]}" }});'
            )

    async def set_geolocation(self, latitude: float, longitude: float) -> None:
        """设置地理位置"""
        await self._context.set_geolocation({"latitude": latitude, "longitude": longitude})
        await self._context.grant_permissions(["geolocation"])