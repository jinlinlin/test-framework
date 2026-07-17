"""
测试运行器 - 命令模式

封装测试任务，支持执行、取消、状态查询等操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from ...core.playwright import PlaywrightManager, BrowserConfig
from ...core.playwright.action_chains import ActionChains
from ...core.playwright.assertion_chain import AssertionChain

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TestCommand:
    """测试命令"""
    name: str = ""
    action: str = ""
    selector: str = ""
    value: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """测试结果"""
    status: TestStatus = TestStatus.PENDING
    message: str = ""
    duration: float = 0.0
    screenshot_path: Optional[str] = None


class TestRunner:
    """
    测试运行器

    封装测试任务，支持执行、取消、状态查询等操作。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._playwright_manager: Optional[PlaywrightManager] = None
        self._page = None
        self._status = TestStatus.PENDING
        self._result = TestResult()
        self._task: Optional[asyncio.Task] = None
        self._cancelled = False

    @property
    def status(self) -> TestStatus:
        """获取测试状态"""
        return self._status

    @property
    def result(self) -> TestResult:
        """获取测试结果"""
        return self._result

    async def initialize(self) -> None:
        """初始化Playwright"""
        browser_config = self._build_browser_config()
        self._playwright_manager = await PlaywrightManager.get_instance()
        await self._playwright_manager.initialize(browser_config)
        self._page = self._playwright_manager.current_page
        logger.info("TestRunner initialized")

    def _build_browser_config(self) -> BrowserConfig:
        """构建浏览器配置"""
        browser_config = self._config.get("browser", {})
        return BrowserConfig(
            headless=browser_config.get("headless", True),
            viewport={
                "width": browser_config.get("viewport_width", 1920),
                "height": browser_config.get("viewport_height", 1080),
            },
            slow_mo=browser_config.get("slow_mo", 0),
        )

    async def execute(self, commands: list[TestCommand]) -> TestResult:
        """
        执行测试命令序列

        Args:
            commands: 测试命令列表

        Returns:
            测试结果
        """
        self._status = TestStatus.RUNNING
        start_time = asyncio.get_event_loop().time()

        try:
            for cmd in commands:
                if self._cancelled:
                    break

                await self._execute_command(cmd)
                logger.debug(f"Executed command: {cmd.action} {cmd.selector}")

            if self._cancelled:
                self._status = TestStatus.CANCELLED
                self._result = TestResult(
                    status=TestStatus.CANCELLED,
                    message="测试已取消",
                    duration=asyncio.get_event_loop().time() - start_time,
                )
            else:
                self._status = TestStatus.PASSED
                self._result = TestResult(
                    status=TestStatus.PASSED,
                    message="测试通过",
                    duration=asyncio.get_event_loop().time() - start_time,
                )
        except Exception as e:
            self._status = TestStatus.FAILED
            screenshot_path = await self._capture_screenshot()
            self._result = TestResult(
                status=TestStatus.FAILED,
                message=str(e),
                duration=asyncio.get_event_loop().time() - start_time,
                screenshot_path=screenshot_path,
            )
            logger.error(f"Test execution failed: {e}")

        return self._result

    async def _execute_command(self, cmd: TestCommand) -> None:
        """执行单个命令"""
        action = cmd.action.lower()
        selector = cmd.selector
        value = cmd.value
        options = cmd.options

        if action == "navigate":
            await self._page.goto(value, wait_until="networkidle")
        elif action == "click":
            await self._page.click(selector, **options)
        elif action == "fill":
            await self._page.fill(selector, value)
        elif action == "type":
            await self._page.type(selector, value, delay=options.get("delay", 50))
        elif action == "select":
            await self._page.select_option(selector, value)
        elif action == "hover":
            await self._page.hover(selector)
        elif action == "wait":
            await self._page.wait_for_selector(selector, timeout=options.get("timeout", 30000))
        elif action == "wait_for_url":
            await self._page.wait_for_url(value, timeout=options.get("timeout", 30000))
        elif action == "wait_for_navigation":
            async with self._page.expect_navigation(timeout=options.get("timeout", 30000)):
                pass
        elif action == "assert_visible":
            from playwright.async_api import expect
            await expect(self._page.locator(selector)).to_be_visible()
        elif action == "assert_hidden":
            from playwright.async_api import expect
            await expect(self._page.locator(selector)).to_be_hidden()
        elif action == "assert_text":
            from playwright.async_api import expect
            await expect(self._page.locator(selector)).to_have_text(value)
        elif action == "assert_url":
            from playwright.async_api import expect
            await expect(self._page).to_have_url(value)
        elif action == "assert_title":
            from playwright.async_api import expect
            await expect(self._page).to_have_title(value)
        elif action == "screenshot":
            await self._page.screenshot(path=value)
        else:
            logger.warning(f"Unknown command: {action}")

    async def _capture_screenshot(self) -> Optional[str]:
        """捕获截图"""
        try:
            import os
            screenshot_dir = "artifacts/screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)
            path = f"{screenshot_dir}/failure_{asyncio.get_event_loop().time()}.png"
            await self._page.screenshot(path=path, full_page=True)
            return path
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")
            return None

    async def cancel(self) -> None:
        """取消测试"""
        self._cancelled = True
        if self._task:
            self._task.cancel()
        logger.info("Test cancelled")

    async def cleanup(self) -> None:
        """清理资源"""
        if self._playwright_manager:
            await self._playwright_manager.close()
            PlaywrightManager.reset()
        logger.info("TestRunner cleaned up")

    async def run_action_chain(self, actions: ActionChains) -> None:
        """运行操作链"""
        await actions.perform()

    async def run_assertion_chain(self, assertions: AssertionChain) -> None:
        """运行断言链"""
        await assertions.perform()