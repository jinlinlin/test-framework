"""
断言接口 — 定义断言能力契约。

设计模式：建造者模式（Builder）
职责：定义UI元素的断言操作标准接口，支持链式断言。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IAssertable(ABC):
    """
    断言接口。

    定义页面元素的断言操作能力，支持可见性、文本、属性等多种断言。
    """

    @abstractmethod
    async def assert_visible(self, selector: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素可见。"""
        ...

    @abstractmethod
    async def assert_hidden(self, selector: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素隐藏。"""
        ...

    @abstractmethod
    async def assert_text(self, selector: str, expected_text: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素文本。"""
        ...

    @abstractmethod
    async def assert_attribute(
        self, selector: str, attribute: str, expected_value: str, timeout: Optional[int] = None
    ) -> "IAssertable":
        """断言元素属性。"""
        ...

    @abstractmethod
    async def assert_css_property(
        self, selector: str, property_name: str, expected_value: str, timeout: Optional[int] = None
    ) -> "IAssertable":
        """断言CSS属性。"""
        ...

    @abstractmethod
    async def assert_count(self, selector: str, expected_count: int, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素数量。"""
        ...

    @abstractmethod
    async def assert_url(self, url_pattern: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言URL。"""
        ...

    @abstractmethod
    async def assert_title(self, expected_title: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言页面标题。"""
        ...

    @abstractmethod
    async def assert_enabled(self, selector: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素启用状态。"""
        ...

    @abstractmethod
    async def assert_checked(self, selector: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素勾选状态。"""
        ...

    @abstractmethod
    async def assert_focused(self, selector: str, timeout: Optional[int] = None) -> "IAssertable":
        """断言元素聚焦状态。"""
        ...