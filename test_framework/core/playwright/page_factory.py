"""
页面工厂 - 工厂模式

负责创建和管理Page Object实例。

设计模式：工厂模式（Factory）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from playwright.async_api import Page

from .base_page import BasePage

logger = logging.getLogger(__name__)


class PageFactory:
    """
    页面工厂

    通过注册表管理页面类，支持动态创建页面实例。
    """

    _registry: Dict[str, Type[BasePage]] = {}

    @classmethod
    def register(cls, page_name: str, page_class: Type[BasePage]) -> None:
        """
        注册页面类

        Args:
            page_name: 页面名称
            page_class: 页面类
        """
        cls._registry[page_name] = page_class
        logger.debug(f"Registered page: {page_name} -> {page_class.__name__}")

    @classmethod
    def create(cls, page_name: str, page: Page, **kwargs: Any) -> BasePage:
        """
        创建页面实例

        Args:
            page_name: 页面名称
            page: Playwright Page对象
            **kwargs: 额外参数

        Returns:
            页面实例

        Raises:
            ValueError: 页面未注册时抛出
        """
        if page_name not in cls._registry:
            raise ValueError(f"Page '{page_name}' not registered. Available: {list(cls._registry.keys())}")

        page_class = cls._registry[page_name]
        instance = page_class(page, **kwargs)
        logger.debug(f"Created page instance: {page_name}")
        return instance

    @classmethod
    def available_pages(cls) -> list[str]:
        """获取所有已注册页面名称"""
        return list(cls._registry.keys())

    @classmethod
    def get_page_class(cls, page_name: str) -> Optional[Type[BasePage]]:
        """获取页面类"""
        return cls._registry.get(page_name)