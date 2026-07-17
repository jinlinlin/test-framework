"""
可插拔接口 — 定义插件的统一契约。

所有插件（内置和用户自定义）必须实现此接口，
支持插件信息查询和激活/停用控制。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IPluggable(ABC):
    """可插拔接口 — 插件的统一契约。"""

    @abstractmethod
    def get_plugin_info(self) -> Dict[str, Any]:
        """
        获取插件元信息。

        Returns:
            包含 id, name, version, description, author, dependencies 的字典。
        """

    @abstractmethod
    def activate(self) -> None:
        """
        激活插件 — 注册引擎、钩子、扩展功能。

        由 PluginManager 在加载后调用。
        """

    @abstractmethod
    def deactivate(self) -> None:
        """
        停用插件 — 注销引擎、钩子、释放资源。

        由 PluginManager 在卸载前调用。
        """
