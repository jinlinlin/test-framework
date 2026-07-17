"""
测试基类 - 提供测试用例的通用能力

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import pytest

from .playwright_manager import BrowserConfig, PlaywrightManager

logger = logging.getLogger(__name__)


class BaseTest:
    """
    测试基类

    提供测试用例的通用能力，包括浏览器初始化、页面管理、测试数据管理等。
    """

    @pytest.fixture(autouse=True, scope="function")
    async def setup_playwright(self, request: pytest.FixtureRequest) -> None:
        """Playwright初始化夹具"""
        config = self._get_browser_config(request)
        self._playwright_manager = await PlaywrightManager.get_instance()
        await self._playwright_manager.initialize(config)
        self._page = self._playwright_manager.current_page

        yield

        await self._playwright_manager.close()
        PlaywrightManager.reset()

    def _get_browser_config(self, request: pytest.FixtureRequest) -> BrowserConfig:
        """获取浏览器配置"""
        config = BrowserConfig()
        config.headless = request.config.getoption("--headless", True)
        return config

    @property
    def page(self) -> Any:
        """获取当前页面"""
        return self._page

    @property
    def playwright_manager(self) -> PlaywrightManager:
        """获取Playwright管理器"""
        return self._playwright_manager

    async def navigate_to(self, url: str) -> None:
        """导航到指定URL"""
        await self._page.goto(url, wait_until="networkidle")

    async def take_screenshot(self, name: str = "screenshot") -> str:
        """
        截取测试截图

        Args:
            name: 截图名称

        Returns:
            截图保存路径
        """
        screenshot_dir = os.path.join("artifacts", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, f"{name}.png")
        await self._page.screenshot(path=path, full_page=True)
        return path

    async def start_trace(self, name: str = "trace") -> None:
        """开始追踪"""
        await self._playwright_manager.start_trace(name)

    async def stop_trace(self, name: str = "trace") -> None:
        """停止追踪并保存"""
        trace_dir = os.path.join("artifacts", "traces")
        os.makedirs(trace_dir, exist_ok=True)
        path = os.path.join(trace_dir, f"{name}.zip")
        await self._playwright_manager.stop_trace(path)