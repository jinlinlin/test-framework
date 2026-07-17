"""
原生桥接模块 — 在 Python 进程内直接调用模块/类/函数。

职责：支持动态导入和反射调用，无需启动子进程，
      适合框架内部模块间的高频调用。
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NativeBridge:
    """
    原生桥接器 — 在当前 Python 进程内执行动态导入和反射调用。

    支持：
    - 根据模块路径字符串动态导入
    - 根据名称调用类/函数/方法
    - 链式调用（obj.method().sub_method()）
    """

    def call(self, module_path: str, callable_name: str, *args: Any, **kwargs: Any) -> Any:
        """
        动态导入模块并调用其中的可调用对象。

        Args:
            module_path: Python 模块路径（如 'test_framework.engines.base'）。
            callable_name: 可调用对象名称（如 'BaseEngine'）。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            调用结果。

        Raises:
            ImportError: 模块不存在。
            AttributeError: 可调用对象不存在。
        """
        module = self.load_module(module_path)
        callable_obj = getattr(module, callable_name)

        logger.debug(f"原生调用: {module_path}.{callable_name}")
        return callable_obj(*args, **kwargs)

    def load_module(self, module_path: str) -> Any:
        """
        动态导入并返回模块对象。

        Args:
            module_path: Python 模块路径。

        Returns:
            导入的模块对象。

        Raises:
            ImportError: 模块不存在时抛出。
        """
        module = importlib.import_module(module_path)
        logger.debug(f"动态导入模块: {module_path}")
        return module

    def invoke(self, obj: Any, method: str, *args: Any, **kwargs: Any) -> Any:
        """
        在已有对象上反射调用方法。

        Args:
            obj: 目标对象实例。
            method: 方法名称。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            调用结果。

        Raises:
            AttributeError: 方法不存在时抛出。
        """
        func = getattr(obj, method)
        logger.debug(f"反射调用: {type(obj).__name__}.{method}")
        return func(*args, **kwargs)

    def create_instance(self, class_path: str, *args: Any, **kwargs: Any) -> Any:
        """
        根据完整路径创建类实例。

        Args:
            class_path: 完整类路径（如 'test_framework.core.container.Container'）。
            *args: 构造函数位置参数。
            **kwargs: 构造函数关键字参数。

        Returns:
            创建的类实例。
        """
        module_path, class_name = class_path.rsplit(".", 1)
        module = self.load_module(module_path)
        cls = getattr(module, class_name)
        return cls(*args, **kwargs)
