"""
等待条件 - 策略模式

提供多种等待条件，支持灵活的等待策略组合。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from playwright.async_api import Locator, Page, expect

logger = logging.getLogger(__name__)


class WaitCondition(ABC):
    """等待条件基类"""

    @abstractmethod
    async def wait(self, page: Page, **kwargs: Any) -> None:
        """执行等待"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """条件名称"""
        ...


class VisibilityCondition(WaitCondition):
    """等待可见条件"""

    def __init__(self, selector: str) -> None:
        self._selector = selector

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page.locator(self._selector)).to_be_visible(timeout=timeout)

    @property
    def name(self) -> str:
        return "visibility"


class PresenceCondition(WaitCondition):
    """等待存在条件"""

    def __init__(self, selector: str) -> None:
        self._selector = selector

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page.locator(self._selector)).to_be_attached(timeout=timeout)

    @property
    def name(self) -> str:
        return "presence"


class HiddenCondition(WaitCondition):
    """等待隐藏条件"""

    def __init__(self, selector: str) -> None:
        self._selector = selector

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page.locator(self._selector)).to_be_hidden(timeout=timeout)

    @property
    def name(self) -> str:
        return "hidden"


class ClickableCondition(WaitCondition):
    """等待可点击条件"""

    def __init__(self, selector: str) -> None:
        self._selector = selector

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page.locator(self._selector)).to_be_enabled(timeout=timeout)

    @property
    def name(self) -> str:
        return "clickable"


class EnabledCondition(WaitCondition):
    """等待启用条件"""

    def __init__(self, selector: str) -> None:
        self._selector = selector

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page.locator(self._selector)).to_be_enabled(timeout=timeout)

    @property
    def name(self) -> str:
        return "enabled"


class TextChangeCondition(WaitCondition):
    """等待文本变化条件"""

    def __init__(self, selector: str, expected_text: str) -> None:
        self._selector = selector
        self._expected_text = expected_text

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page.locator(self._selector)).to_have_text(self._expected_text, timeout=timeout)

    @property
    def name(self) -> str:
        return "text_change"


class NetworkIdleCondition(WaitCondition):
    """等待网络空闲条件"""

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await page.wait_for_load_state("networkidle", timeout=timeout)

    @property
    def name(self) -> str:
        return "network_idle"


class LoadStateCondition(WaitCondition):
    """等待加载状态条件"""

    def __init__(self, state: str = "networkidle") -> None:
        self._state = state

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await page.wait_for_load_state(self._state, timeout=timeout)

    @property
    def name(self) -> str:
        return "load_state"


class UrlChangeCondition(WaitCondition):
    """等待URL变化条件"""

    def __init__(self, url_pattern: str) -> None:
        self._url_pattern = url_pattern

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await expect(page).to_have_url(self._url_pattern, timeout=timeout)

    @property
    def name(self) -> str:
        return "url_change"


class NavigationCondition(WaitCondition):
    """等待导航条件"""

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        async with page.expect_navigation(timeout=timeout):
            pass

    @property
    def name(self) -> str:
        return "navigation"


class ResponseCondition(WaitCondition):
    """等待响应条件"""

    def __init__(self, url_pattern: str, status_code: Optional[int] = None) -> None:
        self._url_pattern = url_pattern
        self._status_code = status_code

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        response = await page.wait_for_response(
            lambda r: self._url_pattern in r.url and (self._status_code is None or r.status == self._status_code),
            timeout=timeout
        )
        if self._status_code and response.status != self._status_code:
            raise RuntimeError(f"Expected status {self._status_code}, got {response.status}")

    @property
    def name(self) -> str:
        return "response"


class RequestCondition(WaitCondition):
    """等待请求条件"""

    def __init__(self, url_pattern: str) -> None:
        self._url_pattern = url_pattern

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        await page.wait_for_request(lambda r: self._url_pattern in r.url, timeout=timeout)

    @property
    def name(self) -> str:
        return "request"


class ConsoleLogCondition(WaitCondition):
    """等待控制台日志条件"""

    def __init__(self, message_pattern: str, log_type: str = "log") -> None:
        self._message_pattern = message_pattern
        self._log_type = log_type

    async def wait(self, page: Page, **kwargs: Any) -> None:
        timeout = kwargs.get("timeout", 30000)
        async with page.expect_console_message(
            lambda msg: msg.type == self._log_type and self._message_pattern in msg.text,
            timeout=timeout
        ):
            pass

    @property
    def name(self) -> str:
        return "console_log"


class WaitConditions:
    """
    等待条件管理器

    支持多种等待条件，提供便捷的等待方法。
    """

    @staticmethod
    async def wait_for_visibility(page: Page, selector: str, timeout: int = 30000) -> None:
        """等待元素可见"""
        await VisibilityCondition(selector).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_presence(page: Page, selector: str, timeout: int = 30000) -> None:
        """等待元素存在"""
        await PresenceCondition(selector).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_hidden(page: Page, selector: str, timeout: int = 30000) -> None:
        """等待元素隐藏"""
        await HiddenCondition(selector).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_clickable(page: Page, selector: str, timeout: int = 30000) -> None:
        """等待元素可点击"""
        await ClickableCondition(selector).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_enabled(page: Page, selector: str, timeout: int = 30000) -> None:
        """等待元素启用"""
        await EnabledCondition(selector).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_text_change(page: Page, selector: str, expected_text: str, timeout: int = 30000) -> None:
        """等待文本变化"""
        await TextChangeCondition(selector, expected_text).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_network_idle(page: Page, timeout: int = 30000) -> None:
        """等待网络空闲"""
        await NetworkIdleCondition().wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_load_state(page: Page, state: str = "networkidle", timeout: int = 30000) -> None:
        """等待加载状态"""
        await LoadStateCondition(state).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_url_change(page: Page, url_pattern: str, timeout: int = 30000) -> None:
        """等待URL变化"""
        await UrlChangeCondition(url_pattern).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_navigation(page: Page, timeout: int = 30000) -> None:
        """等待导航完成"""
        await NavigationCondition().wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_response(page: Page, url_pattern: str, status_code: Optional[int] = None, timeout: int = 30000) -> None:
        """等待响应"""
        await ResponseCondition(url_pattern, status_code).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_request(page: Page, url_pattern: str, timeout: int = 30000) -> None:
        """等待请求"""
        await RequestCondition(url_pattern).wait(page, timeout=timeout)

    @staticmethod
    async def wait_for_console_log(page: Page, message_pattern: str, log_type: str = "log", timeout: int = 30000) -> None:
        """等待控制台日志"""
        await ConsoleLogCondition(message_pattern, log_type).wait(page, timeout=timeout)