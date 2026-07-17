"""
适配器工厂 — 根据类型和实现名创建适配器实例（工厂模式）。

设计模式：工厂模式（Factory Pattern）
职责：维护 adapter_type → impl_name → AdapterClass 的注册表，
      按需创建适配器实例。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Type

from .base import BaseAdapter

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    适配器工厂（工厂模式）。

    注册表结构::

        {
            "http": {
                "httpx": HttpxAdapter,
                "requests": RequestsAdapter,
                "aiohttp": AiohttpAdapter,
            },
            "browser": {
                "playwright": PlaywrightAdapter,
                "selenium": SeleniumAdapter,
            },
            ...
        }

    Attributes:
        _registry: 三级映射表。
        _defaults: 每种类型的默认实现名。
    """

    _registry: Dict[str, Dict[str, Type[BaseAdapter]]] = {}
    _defaults: Dict[str, str] = {}

    @classmethod
    def register(
        cls,
        adapter_type: str,
        impl_name: str,
        adapter_cls: Type[BaseAdapter],
        is_default: bool = False,
    ) -> None:
        """
        注册适配器类。

        Args:
            adapter_type: 适配器类型（http / browser / ...）。
            impl_name: 实现名称（httpx / playwright / ...）。
            adapter_cls: 适配器类。
            is_default: 是否设为该类型的默认实现。
        """
        if adapter_type not in cls._registry:
            cls._registry[adapter_type] = {}
        cls._registry[adapter_type][impl_name] = adapter_cls
        if is_default or adapter_type not in cls._defaults:
            cls._defaults[adapter_type] = impl_name
        logger.debug(f"注册适配器: {adapter_type}/{impl_name} → {adapter_cls.__name__}")

    @classmethod
    def create(
        cls,
        adapter_type: str,
        impl_name: str = "",
        **kwargs: Any,
    ) -> BaseAdapter:
        """
        创建适配器实例。

        Args:
            adapter_type: 适配器类型。
            impl_name: 实现名称（为空时使用默认实现）。
            **kwargs: 传递给适配器的额外参数。

        Returns:
            适配器实例。

        Raises:
            ValueError: 未注册的适配器类型或实现。
        """
        impls = cls._registry.get(adapter_type)
        if not impls:
            raise ValueError(f"未注册的适配器类型: {adapter_type}")

        # 使用默认实现
        if not impl_name:
            impl_name = cls._defaults.get(adapter_type, "")

        adapter_cls = impls.get(impl_name)
        if not adapter_cls:
            raise ValueError(
                f"未注册的适配器实现: {adapter_type}/{impl_name}，"
                f"可用: {list(impls.keys())}"
            )

        return adapter_cls(**kwargs)

    @classmethod
    def available(cls, adapter_type: str) -> List[str]:
        """
        获取指定类型的所有可用实现名。

        Args:
            adapter_type: 适配器类型。

        Returns:
            实现名列表。
        """
        impls = cls._registry.get(adapter_type, {})
        return list(impls.keys())

    @classmethod
    def available_types(cls) -> List[str]:
        """获取所有已注册的适配器类型。"""
        return list(cls._registry.keys())


# ===== 自动注册内置适配器 =====
def _auto_register() -> None:
    """导入时自动注册内置适配器。"""
    # HTTP 适配器
    try:
        from .http.httpx_impl import HttpxAdapter
        AdapterFactory.register("http", "httpx", HttpxAdapter, is_default=True)
    except ImportError:
        pass
    try:
        from .http.requests_impl import RequestsAdapter
        AdapterFactory.register("http", "requests", RequestsAdapter)
    except ImportError:
        pass
    try:
        from .http.aiohttp_impl import AiohttpAdapter
        AdapterFactory.register("http", "aiohttp", AiohttpAdapter)
    except ImportError:
        pass

    # 浏览器适配器
    try:
        from .browser.playwright_impl import PlaywrightAdapter
        AdapterFactory.register("browser", "playwright", PlaywrightAdapter, is_default=True)
    except ImportError:
        pass
    try:
        from .browser.selenium_impl import SeleniumAdapter
        AdapterFactory.register("browser", "selenium", SeleniumAdapter)
    except ImportError:
        pass

    # 数据库适配器
    try:
        from .database.asyncpg_impl import AsyncpgAdapter
        AdapterFactory.register("database", "asyncpg", AsyncpgAdapter, is_default=True)
    except ImportError:
        pass
    try:
        from .database.aiomysql_impl import AiomysqlAdapter
        AdapterFactory.register("database", "aiomysql", AiomysqlAdapter)
    except ImportError:
        pass
    try:
        from .database.motor_impl import MotorAdapter
        AdapterFactory.register("database", "motor", MotorAdapter)
    except ImportError:
        pass
    try:
        from .database.redis_impl import RedisAdapter as DbRedisAdapter
        AdapterFactory.register("database", "redis", DbRedisAdapter)
    except ImportError:
        pass

    # 消息队列适配器
    try:
        from .messaging.kafka_impl import KafkaAdapter
        AdapterFactory.register("messaging", "kafka", KafkaAdapter, is_default=True)
    except ImportError:
        pass
    try:
        from .messaging.rabbitmq_impl import RabbitMQAdapter
        AdapterFactory.register("messaging", "rabbitmq", RabbitMQAdapter)
    except ImportError:
        pass

    # 负载发生器适配器
    try:
        from .load_generator.jmeter_impl import JMeterAdapter
        AdapterFactory.register("load_generator", "jmeter", JMeterAdapter)
    except ImportError:
        pass
    try:
        from .load_generator.locust_impl import LocustAdapter
        AdapterFactory.register("load_generator", "locust", LocustAdapter)
    except ImportError:
        pass
    try:
        from .load_generator.k6_impl import K6Adapter
        AdapterFactory.register("load_generator", "k6", K6Adapter, is_default=True)
    except ImportError:
        pass


_auto_register()
