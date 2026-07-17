"""
依赖解析器模块 — 自动分析构造函数参数并从容器注入依赖。

通过 inspect 模块分析类的 __init__ 参数类型，
自动从 Container 中解析对应服务并注入。
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Type

from .container import Container

logger = logging.getLogger(__name__)


class DependencyResolver:
    """
    依赖解析器 — 自动从容器注入构造函数和方法参数。

    分析目标类/方法的类型注解参数，
    从 Container 中自动解析并注入对应服务实例。

    Attributes:
        _container: IoC 容器实例。
    """

    def __init__(self, container: Container) -> None:
        """
        初始化依赖解析器。

        Args:
            container: IoC 容器实例，用于解析服务。
        """
        self._container = container

    def resolve(self, cls: Type) -> Any:
        """
        解析并创建类实例 — 自动注入构造函数参数。

        分析 cls.__init__ 的类型注解参数，
        从容器中解析对应服务，然后调用 cls(**kwargs) 创建实例。

        Args:
            cls: 要实例化的类。

        Returns:
            创建好的类实例。

        Raises:
            KeyError: 当某个参数类型未在容器中注册时抛出。
        """
        init_signature = inspect.signature(cls.__init__)
        kwargs = {}

        for param_name, param in init_signature.parameters.items():
            # 跳过 self 参数
            if param_name == "self":
                continue

            # 获取参数类型注解
            param_type = param.annotation

            # 有类型注解且在容器中注册 → 自动注入
            if param_type is not inspect.Parameter.empty and self._container.has(param_type):
                kwargs[param_name] = self._container.resolve(param_type)
                logger.debug(f"注入依赖: {cls.__name__}.{param_name} → {param_type.__name__}")
            elif param.default is inspect.Parameter.empty:
                # 无类型注解且无默认值 → 无法注入
                logger.warning(
                    f"无法解析参数 {cls.__name__}.{param_name}，"
                    f"类型注解缺失且无默认值"
                )

        return cls(**kwargs)

    def resolve_method(self, obj: Any, method_name: str) -> Any:
        """
        解析方法参数并调用 — 自动注入方法参数。

        Args:
            obj: 目标对象实例。
            method_name: 方法名称。

        Returns:
            方法调用的返回值。
        """
        method = getattr(obj, method_name)
        signature = inspect.signature(method)
        kwargs = {}

        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue
            param_type = param.annotation
            if param_type is not inspect.Parameter.empty and self._container.has(param_type):
                kwargs[param_name] = self._container.resolve(param_type)

        return method(**kwargs)
