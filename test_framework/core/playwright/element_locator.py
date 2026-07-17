"""
元素定位器 - 策略模式

提供多种元素定位策略，支持灵活的定位方式组合。

设计模式：策略模式（Strategy）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)


class LocatorStrategy(ABC):
    """定位策略基类"""

    @abstractmethod
    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        """执行定位"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...


class CSSLocator(LocatorStrategy):
    """CSS选择器定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.locator(value, **kwargs)

    @property
    def name(self) -> str:
        return "css"


class XPathLocator(LocatorStrategy):
    """XPath定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.locator(f"xpath={value}", **kwargs)

    @property
    def name(self) -> str:
        return "xpath"


class TestIdLocator(LocatorStrategy):
    """data-testid定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.locator(f'[data-testid="{value}"]', **kwargs)

    @property
    def name(self) -> str:
        return "test_id"


class TextLocator(LocatorStrategy):
    """文本定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        exact = kwargs.pop("exact", False)
        return page.get_by_text(value, exact=exact, **kwargs)

    @property
    def name(self) -> str:
        return "text"


class RoleLocator(LocatorStrategy):
    """ARIA role定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        name = kwargs.pop("name", None)
        return page.get_by_role(value, name=name, **kwargs)

    @property
    def name(self) -> str:
        return "role"


class PlaceholderLocator(LocatorStrategy):
    """placeholder定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.get_by_placeholder(value, **kwargs)

    @property
    def name(self) -> str:
        return "placeholder"


class LabelLocator(LocatorStrategy):
    """label定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.get_by_label(value, **kwargs)

    @property
    def name(self) -> str:
        return "label"


class AltLocator(LocatorStrategy):
    """alt文本定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.get_by_alt_text(value, **kwargs)

    @property
    def name(self) -> str:
        return "alt"


class TitleLocator(LocatorStrategy):
    """title属性定位策略"""

    def locate(self, page: Page, value: str, **kwargs: Any) -> Locator:
        return page.get_by_title(value, **kwargs)

    @property
    def name(self) -> str:
        return "title"


class ElementLocator:
    """
    元素定位器

    支持多种定位策略，根据配置自动选择合适的策略。
    """

    _strategies: Dict[str, LocatorStrategy] = {
        "css": CSSLocator(),
        "xpath": XPathLocator(),
        "test_id": TestIdLocator(),
        "text": TextLocator(),
        "role": RoleLocator(),
        "placeholder": PlaceholderLocator(),
        "label": LabelLocator(),
        "alt": AltLocator(),
        "title": TitleLocator(),
    }

    @classmethod
    def register_strategy(cls, name: str, strategy: LocatorStrategy) -> None:
        """注册自定义定位策略"""
        cls._strategies[name] = strategy
        logger.debug(f"Registered locator strategy: {name}")

    @classmethod
    def locate(
        cls,
        page: Page,
        selector: str,
        strategy: str = "css",
        **kwargs: Any
    ) -> Locator:
        """
        执行元素定位

        Args:
            page: Playwright Page对象
            selector: 选择器值
            strategy: 定位策略名称
            **kwargs: 额外参数

        Returns:
            定位器

        Raises:
            ValueError: 策略未注册时抛出
        """
        if strategy not in cls._strategies:
            raise ValueError(f"Unknown locator strategy: {strategy}. Available: {list(cls._strategies.keys())}")

        return cls._strategies[strategy].locate(page, selector, **kwargs)

    @classmethod
    def available_strategies(cls) -> list[str]:
        """获取所有可用定位策略"""
        return list(cls._strategies.keys())