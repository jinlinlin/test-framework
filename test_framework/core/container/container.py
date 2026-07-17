"""
IoC 容器模块 — 依赖注入核心容器（单例模式）。

设计模式：单例模式
职责：全局服务容器，管理所有服务的注册与解析。
支持单例（Singleton）和瞬态（Transient）两种生命周期。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from ..models.enums import Lifecycle

logger = logging.getLogger(__name__)


class Container:
    """
    IoC 容器（控制反转容器）— 单例模式。

    管理框架所有核心服务的注册和解析，
    支持单例和瞬态两种生命周期管理。

    Attributes:
        _instance: 单例实例引用。
        _services: 接口 → (实现类, 生命周期) 的注册表。
        _singletons: 单例缓存，已创建的实例缓存。

    Example:
        container = Container()
        container.register(IEventBus, EventBus, Lifecycle.SINGLETON)
        bus = container.resolve(IEventBus)
    """

    _instance: Optional[Container] = None

    def __new__(cls) -> Container:
        """确保全局只有一个 Container 实例。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services = {}
            cls._instance._singletons = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化容器（仅首次生效）。"""
        if self._initialized:
            return
        self._initialized = True
        self._services: Dict[Type, tuple] = {}
        self._singletons: Dict[Type, Any] = {}

    def register(
        self,
        interface: Type,
        implementation: Type,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
    ) -> None:
        """
        注册服务 — 将接口与实现类绑定并指定生命周期。

        Args:
            interface: 接口类型（通常是 ABC 抽象类）。
            implementation: 实现类。
            lifecycle: 生命周期（SINGLETON 或 TRANSIENT），默认 SINGLETON。
        """
        self._services[interface] = (implementation, lifecycle)
        logger.debug(
            f"注册服务: {interface.__name__} → {implementation.__name__} "
            f"(lifecycle={lifecycle.value})"
        )

    def resolve(self, interface: Type) -> Any:
        """
        解析服务 — 根据接口类型获取实例。

        对于 SINGLETON 生命周期，返回缓存的实例（首次调用时创建）。
        对于 TRANSIENT 生命周期，每次调用创建新实例。

        Args:
            interface: 接口类型。

        Returns:
            服务实例。

        Raises:
            KeyError: 当接口未注册时抛出。
        """
        if interface not in self._services:
            raise KeyError(f"服务未注册: {interface.__name__}")

        implementation, lifecycle = self._services[interface]

        if lifecycle == Lifecycle.SINGLETON:
            # 单例模式：缓存并复用实例
            if interface not in self._singletons:
                self._singletons[interface] = implementation()
            return self._singletons[interface]
        else:
            # 瞬态模式：每次创建新实例
            return implementation()

    def has(self, interface: Type) -> bool:
        """
        检查接口是否已注册。

        Args:
            interface: 接口类型。

        Returns:
            已注册返回 True，否则返回 False。
        """
        return interface in self._services

    def unregister(self, interface: Type) -> None:
        """
        注销服务 — 移除接口绑定和缓存实例。

        Args:
            interface: 要注销的接口类型。
        """
        self._services.pop(interface, None)
        self._singletons.pop(interface, None)
        logger.debug(f"注销服务: {interface.__name__}")

    def register_instance(self, interface: Type, instance: Any) -> None:
        """
        直接注册实例 — 将已有实例作为单例注册。

        Args:
            interface: 接口类型。
            instance: 服务实例。
        """
        self._services[interface] = (type(instance), Lifecycle.SINGLETON)
        self._singletons[interface] = instance

    def list_services(self) -> Dict[str, str]:
        """
        列出所有已注册的服务。

        Returns:
            {接口名: 实现类名} 的字典。
        """
        return {
            iface.__name__: impl.__name__
            for iface, (impl, _) in self._services.items()
        }

    def reset(self) -> None:
        """
        重置容器 — 清除所有注册和缓存。

        仅在测试环境中使用。
        """
        self._services.clear()
        self._singletons.clear()
        logger.debug("IoC 容器已重置")

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（仅测试用）。"""
        cls._instance = None
