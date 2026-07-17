"""
插件加载器 — 从文件/包/entry_points 动态加载插件类。

职责：根据 PluginInfo 动态导入并实例化插件类。
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import os
from typing import Any, List, Optional, Type

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    插件加载器。

    支持从文件路径、包路径、entry_points 加载插件类。
    """

    def load_from_file(self, file_path: str) -> Optional[Any]:
        """
        从文件路径加载插件类并实例化。

        Args:
            file_path: Python 文件路径。

        Returns:
            插件实例，加载失败返回 None。
        """
        if not os.path.exists(file_path):
            logger.error(f"插件文件不存在: {file_path}")
            return None

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找插件类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and hasattr(attr, "get_plugin_info")
                    and attr_name != "IPluggable"
                ):
                    return attr()
        except Exception as e:
            logger.error(f"从文件加载插件失败 {file_path}: {e}")
        return None

    def load_from_package(self, package_path: str) -> List[Any]:
        """
        从包路径加载所有插件类。

        Args:
            package_path: 包目录路径。

        Returns:
            插件实例列表。
        """
        instances: List[Any] = []
        if not os.path.isdir(package_path):
            return instances

        for item in os.listdir(package_path):
            if item.endswith(".py") and not item.startswith("_"):
                file_path = os.path.join(package_path, item)
                instance = self.load_from_file(file_path)
                if instance:
                    instances.append(instance)
        return instances

    def load_from_entry_points(
        self, group: str = "uniplore_test_framework.plugins"
    ) -> List[Any]:
        """
        从 setuptools entry_points 加载插件。

        Args:
            group: entry_points 组名。

        Returns:
            插件实例列表。
        """
        instances: List[Any] = []
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group=group)
            for ep in eps:
                try:
                    cls = ep.load()
                    instances.append(cls())
                except Exception as e:
                    logger.error(f"加载 entry_point {ep.name} 失败: {e}")
        except Exception as e:
            logger.debug(f"扫描 entry_points 失败: {e}")
        return instances
