"""
适配器异常模块 — 适配器连接、调用过程中抛出的异常。

使用场景：
    - 适配器连接目标失败（HTTP/数据库/消息队列/浏览器）
    - 适配器方法调用异常
    - 适配器不支持的操作
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import FrameworkException


class AdapterException(FrameworkException):
    """
    适配器异常的基类。

    当适配器在连接、执行、断开过程中出现错误时抛出。

    Attributes:
        adapter_type: 适配器类型（如 'http', 'database', 'browser'）。
        implementation: 具体实现名称（如 'httpx', 'asyncpg', 'playwright'）。
    """

    DEFAULT_CODE: str = "ADAPTER_ERROR"

    def __init__(
        self,
        message: str,
        adapter_type: Optional[str] = None,
        implementation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化适配器异常。

        Args:
            message: 异常描述信息。
            adapter_type: 适配器类型名称。
            implementation: 具体实现名称。
            details: 附加上下文信息。
        """
        extra_details = details or {}
        if adapter_type:
            extra_details["adapter_type"] = adapter_type
        if implementation:
            extra_details["implementation"] = implementation

        super().__init__(message=message, code=self.DEFAULT_CODE, details=extra_details)
        self.adapter_type: Optional[str] = adapter_type
        self.implementation: Optional[str] = implementation


class AdapterConnectionError(AdapterException):
    """适配器连接目标失败时抛出（如数据库连接超时、HTTP 服务不可达）。"""

    DEFAULT_CODE: str = "ADAPTER_CONNECTION_ERROR"


class AdapterNotAvailableError(AdapterException):
    """请求的适配器实现未注册或不可用时抛出。"""

    DEFAULT_CODE: str = "ADAPTER_NOT_AVAILABLE"


class AdapterOperationError(AdapterException):
    """适配器执行具体操作时失败。"""

    DEFAULT_CODE: str = "ADAPTER_OPERATION_ERROR"
