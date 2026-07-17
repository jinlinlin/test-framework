"""
插件管理器 — 管理插件生命周期：发现 → 加载 → 注册 → 激活 → 停用。

职责：统一管理所有插件的生命周期，
      维护插件注册表，协调钩子系统。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .discovery import PluginDiscovery, PluginInfo
from .hook import PluginHookSystem
from .loader import PluginLoader

logger = logging.getLogger(__name__)


class PluginManager:
    """
    插件管理器。

    管理插件的完整生命周期：
    1. 发现（discover）：扫描目录找到可用插件
    2. 加载（load）：动态导入插件模块
    3. 注册（register）：将插件实例注册到管理器
    4. 激活（activate）：调用插件的 activate 方法
    5. 停用（deactivate）：调用插件的 deactivate 方法
    """

    def __init__(self) -> None:
        """初始化插件管理器。"""
        self._plugins: Dict[str, Any] = {}  # plugin_id -> plugin_instance
        self._plugin_infos: Dict[str, PluginInfo] = {}  # plugin_id -> PluginInfo
        self._discovery = PluginDiscovery()
        self._loader = PluginLoader()
        self._hooks = PluginHookSystem()

    def discover(self, plugin_dirs: List[str]) -> List[PluginInfo]:
        """
        扫描目录发现可用插件。

        Args:
            plugin_dirs: 要扫描的目录列表。

        Returns:
            发现的插件信息列表。
        """
        all_plugins: List[PluginInfo] = []
        for directory in plugin_dirs:
            plugins = self._discovery.scan_directory(directory)
            all_plugins.extend(plugins)

        # 同时扫描 entry_points
        all_plugins.extend(self._discovery.scan_entry_points())

        for p in all_plugins:
            self._plugin_infos[p.id] = p

        logger.info(f"发现 {len(all_plugins)} 个插件")
        return all_plugins

    def load(self, plugin_id: str) -> Optional[Any]:
        """
        加载指定插件。

        Args:
            plugin_id: 插件 ID。

        Returns:
            插件实例，失败返回 None。
        """
        info = self._plugin_infos.get(plugin_id)
        if not info:
            logger.error(f"未发现的插件: {plugin_id}")
            return None

        if info.module_path:
            instance = self._loader.load_from_file(info.module_path)
            if instance:
                self._plugins[plugin_id] = instance
                info.loaded = True
                logger.info(f"插件已加载: {plugin_id}")
                return instance

        return None

    def load_all(self) -> None:
        """加载所有已发现的插件。"""
        for plugin_id in list(self._plugin_infos.keys()):
            if not self._plugin_infos[plugin_id].loaded:
                self.load(plugin_id)

    def unload(self, plugin_id: str) -> None:
        """卸载插件。"""
        self._plugins.pop(plugin_id, None)
        info = self._plugin_infos.get(plugin_id)
        if info:
            info.loaded = False

    def activate(self, plugin_id: str) -> None:
        """激活插件。"""
        plugin = self._plugins.get(plugin_id)
        if plugin and hasattr(plugin, "activate"):
            try:
                plugin.activate()
                info = self._plugin_infos.get(plugin_id)
                if info:
                    info.enabled = True
                logger.info(f"插件已激活: {plugin_id}")
            except Exception as e:
                logger.error(f"激活插件失败 {plugin_id}: {e}")

    def activate_all(self) -> None:
        """激活所有已加载的插件。"""
        for plugin_id in list(self._plugins.keys()):
            self.activate(plugin_id)

    def deactivate(self, plugin_id: str) -> None:
        """停用插件。"""
        plugin = self._plugins.get(plugin_id)
        if plugin and hasattr(plugin, "deactivate"):
            try:
                plugin.deactivate()
                info = self._plugin_infos.get(plugin_id)
                if info:
                    info.enabled = False
            except Exception as e:
                logger.error(f"停用插件失败 {plugin_id}: {e}")

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """获取插件实例。"""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> List[PluginInfo]:
        """列出所有插件信息。"""
        return list(self._plugin_infos.values())

    def get_hooks(self) -> PluginHookSystem:
        """获取钩子系统。"""
        return self._hooks

    def auto_setup(self, plugin_dirs: Optional[List[str]] = None) -> None:
        """
        自动完成插件发现→加载→激活全流程。

        Args:
            plugin_dirs: 插件目录列表（为空时使用默认目录）。
        """
        if plugin_dirs is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            plugin_dirs = [
                os.path.join(base_dir, "builtin"),
                os.path.join(base_dir, "custom"),
            ]

        self.discover(plugin_dirs)
        self.load_all()
        self.activate_all()
