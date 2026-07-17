"""
基础异常模块 — 定义框架异常体系的根异常类。

所有框架自定义异常均继承自 FrameworkException，
便于上层代码通过捕获基类统一处理框架级错误。

异常层级：
    FrameworkException          # 框架异常根类
    ├── ConfigException         # 配置相关异常
    ├── ExecutionException      # 测试执行异常
    │   ├── TimeoutException    # 超时异常
    │   └── AssertionException  # 断言失败异常
    ├── AdapterException        # 适配器异常
    └── PluginException         # 插件异常
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class FrameworkException(Exception):
    """
    框架异常根类。

    所有框架内部抛出的异常均应继承此类，便于外部统一捕获和处理。

    Attributes:
        message: 异常描述信息。
        code: 异常错误码，用于程序化识别异常类型。
        details: 异常附加上下文信息字典，可包含堆栈、参数等调试信息。
    """

    # 默认错误码，子类可覆盖
    DEFAULT_CODE: str = "FRAMEWORK_ERROR"

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化框架异常。

        Args:
            message: 异常描述信息，必须包含足够的上下文便于排查。
            code: 异常错误码，为 None 时使用类默认值 DEFAULT_CODE。
            details: 附加上下文信息，如请求参数、响应内容等。
        """
        super().__init__(message)
        self.message: str = message
        self.code: str = code or self.DEFAULT_CODE
        self.details: Dict[str, Any] = details or {}

    def __str__(self) -> str:
        """返回格式化的异常字符串，包含错误码和消息。"""
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        """返回异常的完整表示，便于调试。"""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"details={self.details!r})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        将异常序列化为字典，便于 JSON 输出或日志记录。

        Returns:
            包含异常类型、消息、错误码和详情的字典。
        """
        return {
            "exception_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }
