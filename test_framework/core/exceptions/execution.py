"""
执行异常模块 — 测试执行过程中抛出的异常。

使用场景：
    - 测试引擎初始化/执行/清理阶段出错
    - 请求超时
    - 断言验证失败
    - 被测服务不可达
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import FrameworkException


class ExecutionException(FrameworkException):
    """
    测试执行异常的基类。

    涵盖引擎初始化失败、用例执行异常、资源采集错误等场景。

    Attributes:
        engine_type: 出问题的引擎类型名称（如 'rest_api'）。
        case_id: 出问题的测试用例 ID（可选）。
    """

    DEFAULT_CODE: str = "EXECUTION_ERROR"

    def __init__(
        self,
        message: str,
        engine_type: Optional[str] = None,
        case_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化执行异常。

        Args:
            message: 异常描述信息。
            engine_type: 出问题的引擎类型。
            case_id: 出问题的测试用例 ID。
            details: 附加上下文信息。
        """
        extra_details = details or {}
        if engine_type:
            extra_details["engine_type"] = engine_type
        if case_id:
            extra_details["case_id"] = case_id

        super().__init__(message=message, code=self.DEFAULT_CODE, details=extra_details)
        self.engine_type: Optional[str] = engine_type
        self.case_id: Optional[str] = case_id


class TimeoutException(ExecutionException):
    """
    超时异常 — 当操作在规定时间内未完成时抛出。

    常见于 HTTP 请求超时、数据库查询超时、浏览器页面加载超时等场景。

    Attributes:
        timeout_seconds: 设定的超时时间（秒）。
    """

    DEFAULT_CODE: str = "TIMEOUT_ERROR"

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化超时异常。

        Args:
            message: 异常描述信息。
            timeout_seconds: 超时时间（秒）。
            details: 附加上下文信息。
        """
        extra_details = details or {}
        if timeout_seconds is not None:
            extra_details["timeout_seconds"] = timeout_seconds
        super().__init__(message=message, details=extra_details)
        self.timeout_seconds: Optional[float] = timeout_seconds


class AssertionException(ExecutionException):
    """
    断言失败异常 — 当测试断言不通过时抛出。

    包含预期值和实际值，便于报告生成和问题定位。

    Attributes:
        expected: 预期值。
        actual: 实际值。
    """

    DEFAULT_CODE: str = "ASSERTION_ERROR"

    def __init__(
        self,
        message: str,
        expected: Any = None,
        actual: Any = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化断言失败异常。

        Args:
            message: 断言失败描述。
            expected: 预期值。
            actual: 实际值。
            details: 附加上下文信息。
        """
        extra_details = details or {}
        extra_details["expected"] = expected
        extra_details["actual"] = actual
        super().__init__(message=message, details=extra_details)
        self.expected: Any = expected
        self.actual: Any = actual


class ServiceUnavailableException(ExecutionException):
    """被测服务不可达异常 — 连接被测目标失败时抛出。"""

    DEFAULT_CODE: str = "SERVICE_UNAVAILABLE"
