"""
可适配接口 — 定义适配器对象的统一契约（适配器模式）。

设计模式：适配器模式（Adapter Pattern）
所有适配器实现此接口，支持类型转换和适配器名称查询。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type


class IAdaptable(ABC):
    """可适配接口 — 适配器对象的统一契约。"""

    @abstractmethod
    def adapt(self, target_type: Type) -> Any:
        """
        将当前适配器转换为目标类型的接口。

        Args:
            target_type: 目标接口类型。

        Returns:
            适配后的对象实例。
        """

    @abstractmethod
    def get_adapter_name(self) -> str:
        """
        获取适配器实现名称。

        Returns:
            适配器名称（如 'httpx', 'asyncpg', 'playwright'）。
        """
