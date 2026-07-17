"""
UI自动化测试引擎。

基于Playwright实现的UI自动化测试引擎，支持多浏览器、网络拦截、
截图、视频录制等功能。

设计模式：模板模式（Template Method）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ...core.models import TestCase, TestMetrics, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ...core.playwright import PlaywrightManager, BrowserConfig
from ..base import BaseEngine

logger = logging.getLogger(__name__)


class UIAutomationEngine(BaseEngine):
    """
    UI自动化测试引擎。

    基于Playwright实现，支持多浏览器、网络拦截、截图、视频录制等功能。
    """

    def __init__(self, config: Dict[str, Any], container: Any) -> None:
        super().__init__(config, container)
        self._playwright_manager: Optional[PlaywrightManager] = None
        self._page = None

    @property
    def engine_type(self) -> TestType:
        return TestType.UI_AUTOMATION

    async def setup(self, target: TargetSystem) -> None:
        """初始化Playwright和浏览器"""
        try:
            browser_config = self._build_browser_config()
            self._playwright_manager = await PlaywrightManager.get_instance()
            await self._playwright_manager.initialize(browser_config)
            self._page = self._playwright_manager.current_page

            if self._config.get("trace", {}).get("enabled", False):
                await self._playwright_manager.start_trace()

            logger.info(f"UI自动化引擎已初始化: browser={browser_config.headless and 'headless' or 'headed'}")
        except ImportError:
            logger.error("playwright 未安装")
            raise
        except Exception as e:
            logger.error(f"UI自动化引擎初始化失败: {e}")
            raise

    def _build_browser_config(self) -> BrowserConfig:
        """构建浏览器配置"""
        browser_config = self._config.get("browser", {})
        return BrowserConfig(
            headless=browser_config.get("headless", True),
            viewport={
                "width": browser_config.get("viewport_width", 1920),
                "height": browser_config.get("viewport_height", 1080),
            },
            device_scale_factor=browser_config.get("device_scale_factor", 1.0),
            locale=browser_config.get("locale", "zh-CN"),
            timezone_id=browser_config.get("timezone_id", "Asia/Shanghai"),
            user_agent=browser_config.get("user_agent"),
            slow_mo=browser_config.get("slow_mo", 0),
            ignore_https_errors=browser_config.get("ignore_https_errors", False),
            record_video_dir=self._config.get("video", {}).get("dir"),
            record_har_path=self._config.get("network", {}).get("har_path"),
            trace_dir=self._config.get("trace", {}).get("dir"),
            screenshot_on_failure=self._config.get("screenshot", {}).get("on_failure", True),
            video_on_failure=self._config.get("video", {}).get("enabled", False),
        )

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """执行单个UI测试用例"""
        try:
            logger.info(f"执行UI测试用例: {case.name}")

            await self._page.goto(target.base_url, wait_until="networkidle")

            for step in case.config.get("steps", []):
                await self._execute_step(step)

            return TestResult(
                case_id=case.id,
                case_name=case.name,
                status=TestStatus.PASSED,
                message="测试通过",
            )
        except Exception as e:
            logger.error(f"UI测试用例执行失败: {e}")
            if self._config.get("screenshot", {}).get("on_failure", True):
                await self._capture_screenshot(case.name)

            return TestResult(
                case_id=case.id,
                case_name=case.name,
                status=TestStatus.FAILED,
                message=str(e),
            )

    async def _execute_step(self, step: Dict[str, Any]) -> None:
        """执行测试步骤"""
        action_type = step.get("action")
        selector = step.get("selector")
        value = step.get("value")

        if action_type == "click":
            await self._page.click(selector)
        elif action_type == "fill":
            await self._page.fill(selector, value)
        elif action_type == "type":
            await self._page.type(selector, value, delay=step.get("delay", 50))
        elif action_type == "select":
            await self._page.select_option(selector, value)
        elif action_type == "hover":
            await self._page.hover(selector)
        elif action_type == "wait":
            await self._page.wait_for_selector(selector, timeout=step.get("timeout", 30000))
        elif action_type == "assert":
            await self._execute_assertion(step)
        else:
            logger.warning(f"未知操作类型: {action_type}")

    async def _execute_assertion(self, assertion: Dict[str, Any]) -> None:
        """执行断言"""
        from playwright.async_api import expect

        assert_type = assertion.get("assert")
        selector = assertion.get("selector")
        expected = assertion.get("expected")

        if assert_type == "visible":
            await expect(self._page.locator(selector)).to_be_visible()
        elif assert_type == "hidden":
            await expect(self._page.locator(selector)).to_be_hidden()
        elif assert_type == "text":
            await expect(self._page.locator(selector)).to_have_text(expected)
        elif assert_type == "attribute":
            await expect(self._page.locator(selector)).to_have_attribute(
                assertion.get("attribute"), expected
            )
        elif assert_type == "count":
            await expect(self._page.locator(selector)).to_have_count(expected)
        elif assert_type == "url":
            await expect(self._page).to_have_url(expected)
        elif assert_type == "title":
            await expect(self._page).to_have_title(expected)
        else:
            logger.warning(f"未知断言类型: {assert_type}")

    async def _capture_screenshot(self, case_name: str) -> None:
        """捕获失败截图"""
        import os

        screenshot_dir = self._config.get("screenshot", {}).get("dir", "artifacts/screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        path = f"{screenshot_dir}/{case_name}_failed.png"
        await self._page.screenshot(path=path, full_page=True)
        logger.info(f"失败截图已保存: {path}")

    async def collect_metrics(self) -> TestMetrics:
        """采集测试指标"""
        return TestMetrics(
            total_cases=len(self._results),
            passed_cases=sum(1 for r in self._results if r.status == TestStatus.PASSED),
            failed_cases=sum(1 for r in self._results if r.status == TestStatus.FAILED),
            skipped_cases=sum(1 for r in self._results if r.status == TestStatus.SKIPPED),
            duration=0,
        )

    async def teardown(self) -> None:
        """清理资源"""
        if self._playwright_manager:
            if self._config.get("trace", {}).get("enabled", False):
                await self._playwright_manager.stop_trace("artifacts/trace.zip")
            await self._playwright_manager.close()
            PlaywrightManager.reset()
        logger.info("UI自动化引擎资源已清理")