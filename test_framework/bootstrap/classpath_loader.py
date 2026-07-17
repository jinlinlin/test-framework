"""
动态类加载器模块 — 根据字符串路径动态导入和实例化类。

支持根据 'package.module.ClassName' 格式的路径字符串
动态加载类，用于插件加载、引擎工厂、适配器工厂等场景。
"""
from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class ClasspathLoader:
    """
    动态类加载器 — 根据字符串路径导入和实例化 Python 类。

    内置类缓存，同一 classpath 不会重复导入。

    Attributes:
        _cache: classpath → Type 的缓存字典。
    """

    _cache: Dict[str, Type] = {}

    @classmethod
    def load_class(cls, classpath: str) -> Type:
        """
        根据字符串路径加载类。

        Args:
            classpath: 类的完整路径（如 'test_framework.engines.base.BaseEngine'）。

        Returns:
            加载到的类对象。

        Raises:
            ImportError: 模块不存在时抛出。
            AttributeError: 类不存在于模块中时抛出。
        """
        # 检查缓存
        if classpath in cls._cache:
            return cls._cache[classpath]

        # 拆分模块路径和类名
        module_path, class_name = classpath.rsplit(".", 1)

        # 动态导入模块
        module = importlib.import_module(module_path)

        # 获取类对象
        klass = getattr(module, class_name)
        cls._cache[classpath] = klass

        logger.debug(f"动态加载类: {classpath}")
        return klass

    @classmethod
    def instantiate(cls, classpath: str, **kwargs: Any) -> Any:
        """
        根据字符串路径加载类并实例化。

        Args:
            classpath: 类的完整路径。
            **kwargs: 传递给构造函数的参数。

        Returns:
            创建好的类实例。
        """
        klass = cls.load_class(classpath)
        return klass(**kwargs)

    @classmethod
    def scan_package(cls, package_path: str) -> List[Type]:
        """
        扫描指定包下的所有类。

        Args:
            package_path: Python 包路径（如 'test_framework.engines'）。

        Returns:
            包下所有类对象的列表。
        """
        classes: List[Type] = []

        try:
            package = importlib.import_module(package_path)
        except ImportError:
            logger.warning(f"包不存在: {package_path}")
            return classes

        # 遍历包下所有子模块
        for _, module_name, _ in pkgutil.walk_packages(
            package.__path__, prefix=package.__name__ + "."
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError as e:
                logger.warning(f"无法导入模块 {module_name}: {e}")
                continue

            # 收集模块中的所有类
            for _, obj in inspect.getmembers(module, inspect.isclass):
                # 仅收集定义在当前模块中的类（排除导入的）
                if obj.__module__ == module.__name__:
                    classes.append(obj)

        logger.debug(f"扫描包 {package_path!r}，发现 {len(classes)} 个类")
        return classes

    @classmethod
    def clear_cache(cls) -> None:
        """清除类缓存（仅测试用）。"""
        cls._cache.clear()
