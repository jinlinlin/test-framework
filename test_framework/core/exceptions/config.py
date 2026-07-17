"""
配置异常模块 — 配置加载、解析、验证过程中抛出的异常。

使用场景：
    - 配置文件不存在或无法读取
    - 配置文件格式错误（YAML/JSON 解析失败）
    - 配置项缺失或类型不匹配
    - 配置 Schema 验证失败
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import FrameworkException


class ConfigException(FrameworkException):
    """
    配置相关异常的基类。

    当配置加载、合并、验证过程中出现错误时抛出此异常。

    Attributes:
        config_path: 出问题的配置文件路径（可选）。
        config_key: 出问题的配置键名（可选）。
    """

    DEFAULT_CODE: str = "CONFIG_ERROR"

    def __init__(
        self,
        message: str,
        config_path: Optional[str] = None,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化配置异常。

        Args:
            message: 异常描述信息。
            config_path: 出问题的配置文件路径。
            config_key: 出问题的配置键名（如 'engines.rest_api.timeout'）。
            details: 附加上下文信息。
        """
        # 将配置路径和键名附加到详情字典中
        extra_details = details or {}
        if config_path:
            extra_details["config_path"] = config_path
        if config_key:
            extra_details["config_key"] = config_key

        super().__init__(message=message, code=self.DEFAULT_CODE, details=extra_details)
        self.config_path: Optional[str] = config_path
        self.config_key: Optional[str] = config_key


class ConfigNotFoundException(ConfigException):
    """配置文件不存在时抛出。"""

    DEFAULT_CODE: str = "CONFIG_NOT_FOUND"


class ConfigParseError(ConfigException):
    """配置文件解析失败（格式错误）时抛出。"""

    DEFAULT_CODE: str = "CONFIG_PARSE_ERROR"


class ConfigValidationError(ConfigException):
    """配置 Schema 验证失败时抛出。"""

    DEFAULT_CODE: str = "CONFIG_VALIDATION_ERROR"
