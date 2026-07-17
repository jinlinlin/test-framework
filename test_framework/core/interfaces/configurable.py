"""
可配置接口 — 定义支持配置加载和验证的统一契约。

引擎、适配器、策略等组件实现此接口，支持从配置文件加载参数。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IConfigurable(ABC):
    """可配置接口 — 支持配置加载和验证的组件契约。"""

    @abstractmethod
    def load_config(self, config: Dict[str, Any]) -> None:
        """
        从配置字典加载参数。

        Args:
            config: 配置字典，通常来自 YAML/JSON 配置文件。
        """

    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        验证当前配置的有效性和完整性。

        Returns:
            错误消息列表，空列表表示配置有效。
        """

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        获取当前生效的配置字典。

        Returns:
            当前配置字典的副本。
        """
