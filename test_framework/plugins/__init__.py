"""插件系统子包 — 插件管理器、加载器、钩子、发现。"""
from .manager import PluginManager
from .hook import PluginHookSystem
from .discovery import PluginDiscovery, PluginInfo

__all__ = ["PluginManager", "PluginHookSystem", "PluginDiscovery", "PluginInfo"]
