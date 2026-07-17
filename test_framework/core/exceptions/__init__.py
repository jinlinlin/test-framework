"""
core.exceptions 包 — 框架异常体系定义。

提供框架全部自定义异常类，按职责分为五大类：
    - FrameworkException: 框架异常根类
    - ConfigException: 配置相关异常
    - ExecutionException: 测试执行异常（含 Timeout/Assertion）
    - AdapterException: 适配器异常
    - PluginException: 插件异常

所有异常均包含 message（描述）、code（错误码）、details（上下文）三个字段，
支持 to_dict() 序列化。
"""
from .base import FrameworkException
from .config import (
    ConfigException,
    ConfigNotFoundException,
    ConfigParseError,
    ConfigValidationError,
)
from .execution import (
    AssertionException,
    ExecutionException,
    ServiceUnavailableException,
    TimeoutException,
)
from .adapter import (
    AdapterConnectionError,
    AdapterException,
    AdapterNotAvailableError,
    AdapterOperationError,
)
from .plugin import (
    PluginActivationError,
    PluginDependencyError,
    PluginException,
    PluginLoadError,
    PluginNotFoundError,
)

__all__ = [
    # 根异常
    "FrameworkException",
    # 配置异常
    "ConfigException",
    "ConfigNotFoundException",
    "ConfigParseError",
    "ConfigValidationError",
    # 执行异常
    "ExecutionException",
    "TimeoutException",
    "AssertionException",
    "ServiceUnavailableException",
    # 适配器异常
    "AdapterException",
    "AdapterConnectionError",
    "AdapterNotAvailableError",
    "AdapterOperationError",
    # 插件异常
    "PluginException",
    "PluginNotFoundError",
    "PluginLoadError",
    "PluginDependencyError",
    "PluginActivationError",
]
