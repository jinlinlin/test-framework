"""
服务注册表模块 — 基于名称和标签的服务注册与发现。

补充 Container 的类型注册机制，支持通过字符串名称和标签查询服务，
适用于插件注册、动态引擎发现等场景。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    服务注册表 — 基于名称和标签的服务管理。

    与 Container（基于类型）互补，支持字符串名称注册和标签查询。

    Attributes:
        _services: 名称 → 服务实例的映射。
        _tags: 标签 → 服务名称列表的映射。
    """

    def __init__(self) -> None:
        """初始化空的服务注册表。"""
        self._services: Dict[str, Any] = {}
        self._tags: Dict[str, List[str]] = defaultdict(list)

    def register(self, name: str, service: Any, tags: Optional[List[str]] = None) -> None:
        """
        注册服务。

        Args:
            name: 服务名称（唯一标识）。
            service: 服务实例。
            tags: 标签列表，用于分类查询。
        """
        self._services[name] = service
        if tags:
            for tag in tags:
                if name not in self._tags[tag]:
                    self._tags[tag].append(name)
        logger.debug(f"注册服务: {name} (tags={tags})")

    def get(self, name: str) -> Any:
        """
        根据名称获取服务。

        Args:
            name: 服务名称。

        Returns:
            服务实例。

        Raises:
            KeyError: 服务不存在时抛出。
        """
        if name not in self._services:
            raise KeyError(f"服务未注册: {name}")
        return self._services[name]

    def get_by_tag(self, tag: str) -> List[Any]:
        """
        根据标签获取所有匹配的服务。

        Args:
            tag: 标签名称。

        Returns:
            匹配的服务实例列表。
        """
        names = self._tags.get(tag, [])
        return [self._services[name] for name in names if name in self._services]

    def has(self, name: str) -> bool:
        """检查服务是否已注册。"""
        return name in self._services

    def unregister(self, name: str) -> None:
        """注销服务并清理相关标签。"""
        self._services.pop(name, None)
        for tag_names in self._tags.values():
            if name in tag_names:
                tag_names.remove(name)

    def list_all(self) -> Dict[str, Any]:
        """列出所有已注册的服务。"""
        return dict(self._services)
