"""
适配器抽象基类 — 适配器模式统一接口。

设计模式：适配器模式（Adapter Pattern）
职责：定义所有适配器的统一抽象接口，
      包含连接、断开、状态查询等生命周期方法，
      支持 async with 上下文管理。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """
    适配器抽象基类。

    所有具体适配器（HTTP / 浏览器 / 数据库 / 消息队列 / 负载发生器）
    必须继承此类并实现抽象方法。

    支持 async with 上下文管理::

        async with HttpxAdapter() as adapter:
            await adapter.connect(config)
            response = await adapter.get(url)
    """

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """适配器类型（http / browser / database / messaging / load_generator）。"""
        ...

    @property
    @abstractmethod
    def implementation_name(self) -> str:
        """具体实现名称（如 httpx / playwright / asyncpg）。"""
        ...

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> None:
        """
        建立连接。

        Args:
            config: 连接配置字典。
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接，释放资源。"""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """
        检查连接状态。

        Returns:
            是否已连接。
        """
        ...

    async def __aenter__(self) -> "BaseAdapter":
        """异步上下文管理器入口。"""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口，自动断开连接。"""
        try:
            await self.disconnect()
        except Exception as e:
            logger.warning(f"断开连接异常: {e}")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.adapter_type}, impl={self.implementation_name})>"
