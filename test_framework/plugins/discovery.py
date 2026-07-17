"""
插件发现 — 自动扫描目录和 entry_points 发现可用插件。

职责：扫描 plugins/builtin/ 和 plugins/custom/ 目录，
      发现所有实现了 IPluggable 接口的插件类。
"""
from __future__ import annotations

import importlib
import logging
import os
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """
    插件元信息。

    Attributes:
        id: 插件唯一标识。
        name: 插件名称。
        version: 版本号。
        description: 描述。
        author: 作者。
        entry_class: 入口类全名。
        module_path: 模块文件路径。
        dependencies: 依赖的其他插件 ID 列表。
        enabled: 是否启用。
        loaded: 是否已加载。
    """

    id: str = ""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    entry_class: str = ""
    module_path: str = ""
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True
    loaded: bool = False


class PluginDiscovery:
    """
    插件发现器。

    扫描指定目录，自动发现符合插件规范的 Python 模块。

    使用示例::

        discovery = PluginDiscovery()
        plugins = discovery.scan_directory("./plugins/builtin")
        for p in plugins:
            print(p.name, p.version)
    """

    def scan_directory(self, directory: str) -> List[PluginInfo]:
        """
        扫描目录发现插件。

        Args:
            directory: 目录路径。

        Returns:
            发现的插件信息列表。
        """
        plugins: List[PluginInfo] = []

        if not os.path.isdir(directory):
            logger.debug(f"插件目录不存在: {directory}")
            return plugins

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)

            # 扫描 Python 文件
            if item.endswith(".py") and not item.startswith("_"):
                info = self._scan_file(item_path)
                if info:
                    plugins.append(info)

            # 扫描子包
            elif os.path.isdir(item_path) and os.path.exists(
                os.path.join(item_path, "__init__.py")
            ):
                info = self._scan_package(item_path)
                if info:
                    plugins.append(info)

        logger.debug(f"在 {directory} 发现 {len(plugins)} 个插件")
        return plugins

    def _scan_file(self, file_path: str) -> Optional[PluginInfo]:
        """扫描单个 Python 文件。"""
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找 IPluggable 实现类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and hasattr(attr, "get_plugin_info")
                    and attr_name != "IPluggable"
                ):
                    info = PluginInfo(
                        id=module_name,
                        name=attr_name,
                        entry_class=f"{module_name}.{attr_name}",
                        module_path=file_path,
                    )
                    return info
        except Exception as e:
            logger.debug(f"扫描文件失败 {file_path}: {e}")
        return None

    def _scan_package(self, package_path: str) -> Optional[PluginInfo]:
        """扫描子包。"""
        init_path = os.path.join(package_path, "__init__.py")
        return self._scan_file(init_path)

    def scan_entry_points(self) -> List[PluginInfo]:
        """通过 setuptools entry_points 发现插件。"""
        plugins: List[PluginInfo] = []
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group="uniplore_test_framework.plugins")
            for ep in eps:
                info = PluginInfo(
                    id=ep.name,
                    name=ep.name,
                    entry_class=f"{ep.value}",
                )
                plugins.append(info)
        except Exception as e:
            logger.debug(f"扫描 entry_points 失败: {e}")
        return plugins
