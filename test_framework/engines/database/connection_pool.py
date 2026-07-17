"""
连接池管理器 — 对象池模式。

职责：管理数据库连接复用，支持连接数上下限、空闲超时、
      健康检查，避免频繁创建/销毁连接。

设计模式：对象池模式（Object Pool Pattern）
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    数据库连接池（对象池模式）。

    维护一组数据库连接，支持按需获取和归还，
    自动管理连接生命周期（创建、空闲回收、健康检查）。

    Attributes:
        _dialect: 数据库方言实例。
        _min_size: 连接池最小连接数。
        _max_size: 连接池最大连接数。
        _idle_timeout: 空闲连接超时时间（秒）。
        _queue: 可用连接异步队列。
        _all_conns: 所有已创建连接的集合。
        _in_use: 当前正在使用的连接数。
        _conn_str: 连接字符串。
        _closed: 连接池是否已关闭。
    """

    def __init__(self, dialect: Any, config: Dict[str, Any]) -> None:
        """
        初始化连接池配置。

        配置格式::

            {
                "min_size": 5,          # 最小连接数
                "max_size": 20,         # 最大连接数
                "idle_timeout": 300,    # 空闲超时（秒）
                "health_check": 60,     # 健康检查间隔（秒）
            }

        Args:
            dialect: 数据库方言实例。
            config: 连接池配置字典。
        """
        self._dialect = dialect
        self._min_size: int = config.get("min_size", 5)
        self._max_size: int = config.get("max_size", 20)
        self._idle_timeout: int = config.get("idle_timeout", 300)
        self._health_check_interval: int = config.get("health_check", 60)
        self._queue: Optional[asyncio.Queue] = None
        self._all_conns: set = set()
        self._in_use: int = 0
        self._conn_str: str = ""
        self._closed: bool = False
        self._total_acquired: int = 0
        self._total_released: int = 0

    async def initialize(self, target: Any) -> None:
        """
        初始化连接池，创建最小数量的连接。

        Args:
            target: 目标系统对象（需包含 config 属性获取连接参数）。
        """
        # 生成连接字符串
        target_config = getattr(target, "config", {})
        if isinstance(target_config, dict):
            self._conn_str = self._dialect.get_connection_string(target_config)
        else:
            self._conn_str = str(target_config)

        # 创建异步队列
        self._queue = asyncio.Queue(maxsize=self._max_size)

        # 预创建最小连接数的连接
        for _ in range(self._min_size):
            conn = await self._create_connection()
            await self._queue.put(conn)

        logger.info(
            f"连接池已初始化: min={self._min_size}, max={self._max_size}, "
            f"已创建 {len(self._all_conns)} 个连接"
        )

    async def acquire(self) -> Any:
        """
        从连接池获取一个连接。

        如果队列中有空闲连接则直接返回，否则创建新连接（不超过上限）。
        如果已达上限则等待其他请求释放连接。

        Returns:
            数据库连接对象。

        Raises:
            RuntimeError: 连接池已关闭。
            asyncio.TimeoutError: 获取连接超时。
        """
        if self._closed:
            raise RuntimeError("连接池已关闭")

        # 尝试从队列获取空闲连接
        try:
            conn = self._queue.get_nowait()
            self._in_use += 1
            self._total_acquired += 1
            return conn
        except asyncio.QueueEmpty:
            pass

        # 如果连接总数未达上限，创建新连接
        if len(self._all_conns) < self._max_size:
            conn = await self._create_connection()
            self._in_use += 1
            self._total_acquired += 1
            return conn

        # 已达上限，等待释放
        logger.debug("连接池已满，等待释放连接...")
        conn = await asyncio.wait_for(self._queue.get(), timeout=30)
        self._in_use += 1
        self._total_acquired += 1
        return conn

    async def release(self, conn: Any) -> None:
        """
        归还连接到连接池。

        如果连接池已满或连接异常，则直接关闭连接。

        Args:
            conn: 要归还的数据库连接。
        """
        if self._closed:
            await self._dialect.close_connection(conn)
            return

        self._in_use = max(0, self._in_use - 1)
        self._total_released += 1

        # 如果连接总数超过最小值且队列已满，关闭多余连接
        if len(self._all_conns) > self._min_size and self._queue.full():
            await self._close_connection(conn)
            return

        # 归还到队列
        try:
            self._queue.put_nowait(conn)
        except asyncio.QueueFull:
            # 队列已满，直接关闭
            await self._close_connection(conn)

    async def close(self) -> None:
        """关闭连接池，释放所有连接。"""
        self._closed = True

        # 关闭队列中的空闲连接
        while not self._queue.empty():
            try:
                conn = self._queue.get_nowait()
                await self._dialect.close_connection(conn)
            except asyncio.QueueEmpty:
                break

        # 关闭所有跟踪的连接
        for conn in list(self._all_conns):
            try:
                await self._dialect.close_connection(conn)
            except Exception:
                pass

        self._all_conns.clear()
        self._in_use = 0
        logger.info("连接池已关闭")

    def stats(self) -> Dict[str, int]:
        """
        获取连接池统计信息。

        Returns:
            统计字典，包含：
            - total_connections: 总连接数
            - in_use: 使用中连接数
            - idle: 空闲连接数
            - max_size: 最大连接数
            - min_size: 最小连接数
            - total_acquired: 累计获取次数
            - total_released: 累计归还次数
        """
        return {
            "total_connections": len(self._all_conns),
            "in_use": self._in_use,
            "idle": self._queue.qsize() if self._queue else 0,
            "max_size": self._max_size,
            "min_size": self._min_size,
            "total_acquired": self._total_acquired,
            "total_released": self._total_released,
        }

    # ===== 私有方法 =====

    async def _create_connection(self) -> Any:
        """
        创建新的数据库连接。

        Returns:
            数据库连接对象。
        """
        conn = await self._dialect.create_connection(self._conn_str)
        self._all_conns.add(id(conn))
        return conn

    async def _close_connection(self, conn: Any) -> None:
        """
        关闭并从跟踪集合中移除连接。

        Args:
            conn: 数据库连接。
        """
        self._all_conns.discard(id(conn))
        try:
            await self._dialect.close_connection(conn)
        except Exception as e:
            logger.warning(f"关闭连接异常: {e}")
