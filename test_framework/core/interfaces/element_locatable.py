"""
元素定位接口 — 定义元素定位能力契约。

设计模式：策略模式（Strategy）
职责：定义元素定位的标准接口，支持多种定位策略。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union


class IElementLocatable(ABC):
    """
    元素定位接口。

    定义页面元素的多种定位方式，所有页面对象必须实现此接口。
    """

    @abstractmethod
    def locate(self, selector: str, **kwargs: Any) -> Any:
        """通用定位方法。"""
        ...

    @abstractmethod
    def locate_by_test_id(self, test_id: str) -> Any:
        """通过data-testid定位。"""
        ...

    @abstractmethod
    def locate_by_role(self, role: str, name: Optional[str] = None) -> Any:
        """通过ARIA role定位。"""
        ...

    @abstractmethod
    def locate_by_text(self, text: str, exact: bool = False) -> Any:
        """通过文本定位。"""
        ...

    @abstractmethod
    def locate_by_placeholder(self, placeholder: str) -> Any:
        """通过placeholder定位。"""
        ...

    @abstractmethod
    def locate_by_label(self, label: str) -> Any:
        """通过label定位。"""
        ...

    @abstractmethod
    def locate_by_alt(self, alt: str) -> Any:
        """通过alt文本定位。"""
        ...

    @abstractmethod
    def locate_by_title(self, title: str) -> Any:
        """通过title属性定位。"""
        ...

    @abstractmethod
    async def find_element(self, selector: str, timeout: Optional[int] = None, state: str = "visible") -> Any:
        """查找单个元素。"""
        ...

    @abstractmethod
    async def find_elements(self, selector: str) -> List[Any]:
        """查找多个元素。"""
        ...

    @abstractmethod
    async def wait_for_element(self, selector: str, timeout: Optional[int] = None, state: str = "visible") -> Any:
        """等待元素出现。"""
        ...