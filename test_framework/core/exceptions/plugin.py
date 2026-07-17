"""
插件异常模块 — 插件发现、加载、激活过程中抛出的异常。

使用场景：
    - 插件文件不存在或加载失败
    - 插件依赖不满足
    - 插件激活/停用失败
    - 插件钩子执行异常
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import FrameworkException


class PluginException(FrameworkException):
    """
    插件异常的基类。

    Attributes:
        plugin_id: 出问题的插件 ID（可选）。
    """

    DEFAULT_CODE: str = "PLUGIN_ERROR"

    def __init__(
        self,
        message: str,
        plugin_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化插件异常。

        Args:
            message: 异常描述信息。
            plugin_id: 出问题的插件标识符。
            details: 附加上下文信息。
        """
        extra_details = details or {}
        if plugin_id:
            extra_details["plugin_id"] = plugin_id

        super().__init__(message=message, code=self.DEFAULT_CODE, details=extra_details)
        self.plugin_id: Optional[str] = plugin_id


class PluginNotFoundError(PluginException):
    """请求的插件未注册或文件不存在时抛出。"""

    DEFAULT_CODE: str = "PLUGIN_NOT_FOUND"


class PluginLoadError(PluginException):
    """插件文件加载失败（语法错误、导入错误等）时抛出。"""

    DEFAULT_CODE: str = "PLUGIN_LOAD_ERROR"


class PluginDependencyError(PluginException):
    """插件依赖的其他插件或模块不满足时抛出。"""

    DEFAULT_CODE: str = "PLUGIN_DEPENDENCY_ERROR"


class PluginActivationError(PluginException):
    """插件激活过程中出现错误时抛出。"""

    DEFAULT_CODE: str = "PLUGIN_ACTIVATION_ERROR"
