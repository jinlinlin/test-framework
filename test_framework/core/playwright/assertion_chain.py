"""
断言链 - 建造者模式

提供链式断言能力，支持组合多个断言条件。

设计模式：建造者模式（Builder）
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

from playwright.async_api import Page, expect

logger = logging.getLogger(__name__)


class AssertionStep:
    """断言步骤"""

    def __init__(self, assertion: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._assertion = assertion
        self._args = args
        self._kwargs = kwargs

    async def execute(self, page: Page) -> None:
        """执行断言步骤"""
        await self._assertion(page, *self._args, **self._kwargs)


class AssertionChain:
    """
    断言链

    支持链式调用，组合多个断言条件一次性执行。
    """

    def __init__(self, page: Page) -> None:
        self._page = page
        self._steps: List[AssertionStep] = []

    def visible(self, selector: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加可见性断言"""
        async def _visible(page: Page) -> None:
            await expect(page.locator(selector)).to_be_visible(timeout=timeout)
        self._steps.append(AssertionStep(_visible))
        return self

    def hidden(self, selector: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加隐藏断言"""
        async def _hidden(page: Page) -> None:
            await expect(page.locator(selector)).to_be_hidden(timeout=timeout)
        self._steps.append(AssertionStep(_hidden))
        return self

    def text(self, selector: str, expected_text: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加文本断言"""
        async def _text(page: Page) -> None:
            await expect(page.locator(selector)).to_have_text(expected_text, timeout=timeout)
        self._steps.append(AssertionStep(_text))
        return self

    def attribute(
        self, selector: str, attribute: str, expected_value: str, timeout: Optional[int] = None
    ) -> "AssertionChain":
        """添加属性断言"""
        async def _attribute(page: Page) -> None:
            await expect(page.locator(selector)).to_have_attribute(attribute, expected_value, timeout=timeout)
        self._steps.append(AssertionStep(_attribute))
        return self

    def css_property(
        self, selector: str, property_name: str, expected_value: str, timeout: Optional[int] = None
    ) -> "AssertionChain":
        """添加CSS属性断言"""
        async def _css_property(page: Page) -> None:
            locator = page.locator(selector)
            await locator.wait_for(state="visible", timeout=timeout)
            computed_style = await locator.evaluate(
                f'(el) => window.getComputedStyle(el).getPropertyValue("{property_name}")'
            )
            assert computed_style == expected_value, (
                f"Expected CSS {property_name} to be {expected_value}, got {computed_style}"
            )
        self._steps.append(AssertionStep(_css_property))
        return self

    def count(self, selector: str, expected_count: int, timeout: Optional[int] = None) -> "AssertionChain":
        """添加元素数量断言"""
        async def _count(page: Page) -> None:
            await expect(page.locator(selector)).to_have_count(expected_count, timeout=timeout)
        self._steps.append(AssertionStep(_count))
        return self

    def url(self, url_pattern: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加URL断言"""
        async def _url(page: Page) -> None:
            await expect(page).to_have_url(url_pattern, timeout=timeout)
        self._steps.append(AssertionStep(_url))
        return self

    def title(self, expected_title: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加标题断言"""
        async def _title(page: Page) -> None:
            await expect(page).to_have_title(expected_title, timeout=timeout)
        self._steps.append(AssertionStep(_title))
        return self

    def enabled(self, selector: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加启用状态断言"""
        async def _enabled(page: Page) -> None:
            await expect(page.locator(selector)).to_be_enabled(timeout=timeout)
        self._steps.append(AssertionStep(_enabled))
        return self

    def checked(self, selector: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加勾选状态断言"""
        async def _checked(page: Page) -> None:
            await expect(page.locator(selector)).to_be_checked(timeout=timeout)
        self._steps.append(AssertionStep(_checked))
        return self

    def focused(self, selector: str, timeout: Optional[int] = None) -> "AssertionChain":
        """添加聚焦状态断言"""
        async def _focused(page: Page) -> None:
            await expect(page.locator(selector)).to_be_focused(timeout=timeout)
        self._steps.append(AssertionStep(_focused))
        return self

    async def perform(self) -> None:
        """执行所有断言步骤"""
        logger.debug(f"Performing {len(self._steps)} assertion steps")
        for i, step in enumerate(self._steps):
            try:
                await step.execute(self._page)
                logger.debug(f"Assertion {i + 1} passed")
            except Exception as e:
                logger.error(f"Assertion {i + 1} failed: {e}")
                raise

        self._steps.clear()